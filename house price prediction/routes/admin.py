import os
from datetime import timedelta
from sqlalchemy import func
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from database import db
from database.models import User, Prediction, SavedProperty, FavoriteLocation, ApiUsageLog, ApiCache, utcnow
from routes import admin_required
from services.prediction_service import prediction_service
from services.ai_service import get_provider_status

admin_bp = Blueprint("admin", __name__)


def _collect_admin_stats():
    total_users = User.query.count()
    total_predictions = Prediction.query.count()
    total_saved = SavedProperty.query.count()
    total_fav_locs = FavoriteLocation.query.count()
    active_cache_entries = ApiCache.query.filter(ApiCache.expires_at > utcnow()).count()

    # Most searched locations
    top_locations_q = (
        db.session.query(Prediction.location_name, func.count(Prediction.id).label("cnt"))
        .filter(Prediction.location_name.isnot(None), Prediction.location_name != "")
        .group_by(Prediction.location_name)
        .order_by(func.count(Prediction.id).desc())
        .limit(8)
        .all()
    )
    top_locations = [{"location": row[0], "count": int(row[1])} for row in top_locations_q]

    # Most popular building types
    top_bldg_q = (
        db.session.query(Prediction.bldg_type, func.count(Prediction.id).label("cnt"))
        .filter(Prediction.bldg_type.isnot(None))
        .group_by(Prediction.bldg_type)
        .order_by(func.count(Prediction.id).desc())
        .all()
    )
    popular_property_types = [{"bldg_type": row[0], "count": int(row[1])} for row in top_bldg_q]

    # 14-day prediction activity
    since = utcnow() - timedelta(days=13)
    recent_preds = Prediction.query.filter(Prediction.created_at >= since).all()
    daily_counts = {}
    for offset in range(14):
        day_str = (since + timedelta(days=offset)).strftime("%Y-%m-%d")
        daily_counts[day_str] = 0
    for p in recent_preds:
        d_str = p.created_at.strftime("%Y-%m-%d")
        if d_str in daily_counts:
            daily_counts[d_str] += 1
    activity_series = [{"date": k, "count": v} for k, v in daily_counts.items()]

    # API usage by service
    api_usage_q = (
        db.session.query(
            ApiUsageLog.service_name,
            func.count(ApiUsageLog.id).label("calls"),
            func.avg(ApiUsageLog.latency_ms).label("avg_ms"),
        )
        .group_by(ApiUsageLog.service_name)
        .order_by(func.count(ApiUsageLog.id).desc())
        .all()
    )
    api_usage = [
        {"service": row[0], "calls": int(row[1]), "avg_latency_ms": round(float(row[2] or 0), 1)}
        for row in api_usage_q
    ]

    recent_logs = ApiUsageLog.query.order_by(ApiUsageLog.created_at.desc()).limit(15).all()
    logs_payload = [
        {
            "service": l.service_name,
            "endpoint": l.endpoint,
            "status": l.status_code,
            "cached": l.cached,
            "latency_ms": l.latency_ms,
            "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for l in recent_logs
    ]

    # System health checks
    prediction_service.load()
    health = {
        "ml_model_loaded": prediction_service._loaded and prediction_service.model is not None,
        "encoder_loaded": prediction_service.encoder is not None,
        "database_connected": True,
        "ai_provider": get_provider_status()["active_provider"],
        "cache_entries": active_cache_entries,
        "validation_mape_pct": prediction_service.validation_metrics.get("mape_pct"),
    }

    users = [u.to_dict() for u in User.query.order_by(User.created_at.desc()).limit(25).all()]

    return {
        "totals": {
            "users": total_users,
            "predictions": total_predictions,
            "saved_properties": total_saved,
            "favorite_locations": total_fav_locs,
            "api_calls": ApiUsageLog.query.count(),
        },
        "top_locations": top_locations,
        "popular_property_types": popular_property_types,
        "activity_series": activity_series,
        "api_usage": api_usage,
        "recent_logs": logs_payload,
        "health": health,
        "users": users,
    }


@admin_bp.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    stats = _collect_admin_stats()
    return render_template("admin.html", stats=stats)


@admin_bp.route("/api/admin/stats", methods=["GET"])
@login_required
@admin_required
def api_admin_stats():
    return jsonify(_collect_admin_stats())


@admin_bp.route("/api/admin/cache/clear", methods=["POST"])
@login_required
@admin_required
def api_clear_cache():
    deleted = ApiCache.query.delete()
    db.session.commit()
    return jsonify({"cleared": True, "entries_removed": int(deleted)})


@admin_bp.route("/api/admin/users/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def api_update_user_role(user_id: int):
    if user_id == current_user.id:
        return jsonify({"error": "You cannot modify your own administrator role."}), 400
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({"error": "User not found."}), 404
    new_role = (request.get_json(silent=True) or {}).get("role", "").strip().lower()
    if new_role not in ("user", "admin"):
        return jsonify({"error": "Role must be 'user' or 'admin'."}), 400
    target.role = new_role
    db.session.commit()
    return jsonify({"updated": True, "user": target.to_dict()})
