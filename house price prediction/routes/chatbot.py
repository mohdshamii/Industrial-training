from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
from database import db, limiter
from database.models import ChatMessage, Prediction, FavoriteLocation
from routes import get_or_create_session_token
from services.ai_service import generate_assistant_reply, get_provider_status

chatbot_bp = Blueprint("chatbot", __name__)


def _fetch_user_history(limit: int = 30):
    if current_user.is_authenticated:
        msgs = (
            ChatMessage.query.filter_by(user_id=current_user.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .all()
        )
    else:
        token = get_or_create_session_token()
        msgs = (
            ChatMessage.query.filter_by(session_token=token)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
            .all()
        )
    return list(reversed(msgs))


@chatbot_bp.route("/assistant")
def assistant_page():
    status = get_provider_status()
    history = [m.to_dict() for m in _fetch_user_history(30)]
    return render_template("chatbot.html", provider_status=status, chat_history=history)


@chatbot_bp.route("/api/chat/status", methods=["GET"])
def api_chat_status():
    return jsonify(get_provider_status())


@chatbot_bp.route("/api/chat/history", methods=["GET", "DELETE"])
def api_chat_history():
    if request.method == "DELETE":
        if current_user.is_authenticated:
            ChatMessage.query.filter_by(user_id=current_user.id).delete()
        else:
            token = get_or_create_session_token()
            ChatMessage.query.filter_by(session_token=token).delete()
        db.session.commit()
        return jsonify({"cleared": True})

    return jsonify({"messages": [m.to_dict() for m in _fetch_user_history(40)]})


@chatbot_bp.route("/api/chat", methods=["POST"])
@limiter.limit("45 per hour")
def api_chat():
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message cannot be empty."}), 400
    if len(message) > 2000:
        return jsonify({"error": "Message exceeds 2,000 character limit."}), 400

    token = get_or_create_session_token()
    uid = current_user.id if current_user.is_authenticated else None

    # Gather live user context (latest prediction, recent predictions, favorite locations)
    if uid:
        recent_preds = (
            Prediction.query.filter_by(user_id=uid)
            .order_by(Prediction.created_at.desc())
            .limit(5)
            .all()
        )
        fav_locs = [f.to_dict() for f in FavoriteLocation.query.filter_by(user_id=uid).limit(5).all()]
    else:
        recent_preds = (
            Prediction.query.filter_by(session_token=token)
            .order_by(Prediction.created_at.desc())
            .limit(5)
            .all()
        )
        fav_locs = []

    recent_dicts = [p.to_dict() for p in recent_preds]
    context = {
        "latest_prediction": recent_dicts[0] if recent_dicts else None,
        "recent_predictions": recent_dicts,
        "favorite_locations": fav_locs,
    }

    history = [{"role": m.role, "content": m.content} for m in _fetch_user_history(8)]

    user_msg = ChatMessage(user_id=uid, session_token=token, role="user", content=message)
    db.session.add(user_msg)
    db.session.commit()

    ai_res = generate_assistant_reply(message, context, history)
    assistant_msg = ChatMessage(
        user_id=uid,
        session_token=token,
        role="assistant",
        content=ai_res["reply"],
        provider_used=ai_res["provider"],
    )
    db.session.add(assistant_msg)
    db.session.commit()

    return jsonify(
        {
            "reply": ai_res["reply"],
            "provider": ai_res["provider"],
            "fallback": ai_res["fallback"],
            "message_id": assistant_msg.id,
        }
    )
