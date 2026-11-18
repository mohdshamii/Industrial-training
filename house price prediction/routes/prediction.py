import json
from flask import Blueprint, render_template, request, jsonify, send_file
from flask_login import current_user, login_required
from database import db, limiter
from database.models import Prediction, SavedProperty, utcnow
from routes import get_or_create_session_token
from services.prediction_service import prediction_service
from services.report_service import generate_prediction_pdf
from services.market_service import get_usd_to_inr_rate, format_inr

prediction_bp = Blueprint("prediction", __name__)


@prediction_bp.route("/predict")
def predict_page():
    schema = prediction_service.get_schema()
    fx = get_usd_to_inr_rate()
    if current_user.is_authenticated:
        history = (
            Prediction.query.filter_by(user_id=current_user.id)
            .order_by(Prediction.created_at.desc())
            .limit(12)
            .all()
        )
    else:
        token = get_or_create_session_token()
        history = (
            Prediction.query.filter_by(session_token=token)
            .order_by(Prediction.created_at.desc())
            .limit(12)
            .all()
        )
    return render_template(
        "prediction.html",
        schema=schema,
        fx=fx,
        history=[h.to_dict() for h in history],
        format_inr=format_inr,
    )


@prediction_bp.route("/api/predict/schema", methods=["GET"])
def api_predict_schema():
    return jsonify(prediction_service.get_schema())


@prediction_bp.route("/api/predict", methods=["POST"])
@limiter.limit("60 per hour")
def api_predict():
    payload = request.get_json(silent=True) or {}
    try:
        result = prediction_service.predict(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Prediction failed: {exc}"}), 500

    title = (payload.get("property_title") or "").strip()[:160]
    if not title:
        title = f"{result['input_features']['BldgType']} ({result['input_features']['YearBuilt']}) - {int(result['input_features']['LotArea']):,} sq ft"

    location_name = (payload.get("location_name") or "").strip()[:200]
    lat = payload.get("latitude")
    lon = payload.get("longitude")
    amenities = payload.get("amenities")

    try:
        lat_val = float(lat) if lat not in (None, "") else None
        lon_val = float(lon) if lon not in (None, "") else None
    except (TypeError, ValueError):
        lat_val, lon_val = None, None

    # Allow lightweight live homepage sandbox previews without polluting DB history
    if payload.get("preview") is True:
        return jsonify(
            {
                "id": None,
                "preview": True,
                "property_title": title,
                "location_name": location_name,
                "is_saved": False,
                "report_url": "/predict",
                **result,
            }
        )

    token = get_or_create_session_token()
    record = Prediction(
        user_id=current_user.id if current_user.is_authenticated else None,
        session_token=token,
        property_title=title,
        location_name=location_name,
        latitude=lat_val,
        longitude=lon_val,
        input_features_json=json.dumps(result["input_features"]),
        bldg_type=result["input_features"]["BldgType"],
        ms_zoning=result["input_features"]["MSZoning"],
        lot_area=result["input_features"]["LotArea"],
        total_bsmt_sf=result["input_features"]["TotalBsmtSF"],
        year_built=result["input_features"]["YearBuilt"],
        overall_cond=result["input_features"]["OverallCond"],
        predicted_price_usd=result["predicted_price_usd"],
        predicted_price_inr=result["predicted_price_inr"],
        exchange_rate_used=result["exchange_rate"]["rate"],
        exchange_rate_source=result["exchange_rate"]["source"],
        ensemble_min_usd=result["ensemble_uncertainty"]["min_usd"],
        ensemble_max_usd=result["ensemble_uncertainty"]["max_usd"],
        ensemble_std_usd=result["ensemble_uncertainty"]["std_usd"],
        ensemble_cv=result["ensemble_uncertainty"]["cv"],
        price_per_sqft_inr=result["price_per_sqft_lot_inr"],
        factors_json=json.dumps(result["factors"]),
        amenities_json=json.dumps(amenities) if isinstance(amenities, dict) else None,
    )
    db.session.add(record)
    db.session.commit()

    return jsonify(
        {
            "id": record.id,
            "property_title": record.property_title,
            "location_name": record.location_name,
            "is_saved": record.is_saved,
            "report_url": f"/api/predictions/{record.id}/report.pdf",
            **result,
        }
    )


@prediction_bp.route("/api/predictions/history", methods=["GET"])
def api_predictions_history():
    if current_user.is_authenticated:
        items = (
            Prediction.query.filter_by(user_id=current_user.id)
            .order_by(Prediction.created_at.desc())
            .limit(30)
            .all()
        )
    else:
        token = get_or_create_session_token()
        items = (
            Prediction.query.filter_by(session_token=token)
            .order_by(Prediction.created_at.desc())
            .limit(30)
            .all()
        )
    return jsonify({"predictions": [p.to_dict() for p in items]})


def _can_access_prediction(pred: Prediction) -> bool:
    if current_user.is_authenticated:
        if current_user.is_admin or pred.user_id == current_user.id:
            return True
    token = get_or_create_session_token()
    return pred.session_token == token


@prediction_bp.route("/api/predictions/<int:pred_id>", methods=["GET", "DELETE"])
def api_prediction_item(pred_id: int):
    pred = db.session.get(Prediction, pred_id)
    if not pred or not _can_access_prediction(pred):
        return jsonify({"error": "Prediction record not found."}), 404

    if request.method == "DELETE":
        db.session.delete(pred)
        db.session.commit()
        return jsonify({"deleted": True, "id": pred_id})

    pred.viewed_at = utcnow()
    db.session.commit()
    return jsonify(pred.to_dict())


@prediction_bp.route("/api/predictions/<int:pred_id>/save", methods=["POST"])
@login_required
def api_save_prediction(pred_id: int):
    pred = db.session.get(Prediction, pred_id)
    if not pred or not _can_access_prediction(pred):
        return jsonify({"error": "Prediction not found."}), 404

    pred.user_id = current_user.id
    pred.is_saved = True
    existing = SavedProperty.query.filter_by(user_id=current_user.id, prediction_id=pred.id).first()
    if not existing:
        sp = SavedProperty(
            user_id=current_user.id,
            prediction_id=pred.id,
            title=pred.property_title,
            location_name=pred.location_name,
            latitude=pred.latitude,
            longitude=pred.longitude,
            predicted_price_inr=pred.predicted_price_inr,
            predicted_price_usd=pred.predicted_price_usd,
            lot_area=pred.lot_area,
            total_bsmt_sf=pred.total_bsmt_sf,
            year_built=pred.year_built,
            bldg_type=pred.bldg_type,
            ms_zoning=pred.ms_zoning,
            overall_cond=pred.overall_cond,
            notes=(request.get_json(silent=True) or {}).get("notes", "")[:500],
        )
        db.session.add(sp)
    db.session.commit()
    return jsonify({"saved": True, "prediction_id": pred.id})


@prediction_bp.route("/api/predictions/<int:pred_id>/report.pdf", methods=["GET"])
def api_prediction_report_pdf(pred_id: int):
    pred = db.session.get(Prediction, pred_id)
    if not pred or not _can_access_prediction(pred):
        return jsonify({"error": "Prediction not found or access denied."}), 404

    pdf_path = generate_prediction_pdf(pred)
    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"EstateIQ_Valuation_Report_{pred.id}.pdf",
    )
