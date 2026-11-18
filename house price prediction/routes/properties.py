import json
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user, login_required
from database import db, limiter
from database.models import Prediction, SavedProperty, FavoriteLocation
from routes import get_or_create_session_token
from services.prediction_service import prediction_service
from services.geolocation_service import geocode_location, fetch_nearby_facilities, fetch_weather
from services.investment_service import calculate_emi, calculate_rental_yield
from services.market_service import get_usd_to_inr_rate

properties_bp = Blueprint("properties", __name__)


@properties_bp.route("/compare")
def compare_page():
    schema = prediction_service.get_schema()
    if current_user.is_authenticated:
        preds = (
            Prediction.query.filter_by(user_id=current_user.id)
            .order_by(Prediction.created_at.desc())
            .limit(20)
            .all()
        )
    else:
        token = get_or_create_session_token()
        preds = (
            Prediction.query.filter_by(session_token=token)
            .order_by(Prediction.created_at.desc())
            .limit(20)
            .all()
        )
    return render_template("comparison.html", schema=schema, predictions=[p.to_dict() for p in preds])


@properties_bp.route("/map")
def map_page():
    favs = []
    if current_user.is_authenticated:
        favs = [
            f.to_dict()
            for f in FavoriteLocation.query.filter_by(user_id=current_user.id)
            .order_by(FavoriteLocation.created_at.desc())
            .all()
        ]
    return render_template("map.html", favorite_locations=favs)


@properties_bp.route("/api/geocode", methods=["GET"])
@limiter.limit("45 per hour")
def api_geocode():
    query = request.args.get("q", "").strip()
    limit = request.args.get("limit", 5, type=int)
    res = geocode_location(query, limit=limit)
    status = 400 if (not res.get("results") and "at least 2" in res.get("error", "")) else 200
    return jsonify(res), status


@properties_bp.route("/api/nearby", methods=["GET"])
@limiter.limit("35 per hour")
def api_nearby():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
        radius = int(request.args.get("radius", 3000))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid lat and lon query parameters are required."}), 400

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"error": "Coordinates out of valid WGS84 bounds."}), 400

    data = fetch_nearby_facilities(lat, lon, radius_m=radius)
    return jsonify(data)


@properties_bp.route("/api/weather", methods=["GET"])
@limiter.limit("60 per hour")
def api_weather():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid lat and lon parameters are required."}), 400

    return jsonify(fetch_weather(lat, lon))


@properties_bp.route("/api/locations/favorite", methods=["GET", "POST"])
@login_required
def api_favorite_locations():
    if request.method == "GET":
        favs = FavoriteLocation.query.filter_by(user_id=current_user.id).order_by(FavoriteLocation.created_at.desc()).all()
        return jsonify({"locations": [f.to_dict() for f in favs]})

    data = request.get_json(silent=True) or {}
    name = (data.get("location_name") or "").strip()[:160]
    display_name = (data.get("display_name") or name).strip()[:300]
    try:
        lat = float(data.get("latitude"))
        lon = float(data.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid latitude and longitude are required."}), 400
    if not name:
        return jsonify({"error": "Location name is required."}), 400

    fav = FavoriteLocation(
        user_id=current_user.id,
        location_name=name,
        display_name=display_name,
        latitude=lat,
        longitude=lon,
        amenities_summary_json=json.dumps(data.get("amenities_summary") or {}),
        weather_json=json.dumps(data.get("weather") or {}),
    )
    db.session.add(fav)
    db.session.commit()
    return jsonify({"saved": True, "location": fav.to_dict()}), 201


@properties_bp.route("/api/locations/favorite/<int:loc_id>", methods=["DELETE"])
@login_required
def api_delete_favorite_location(loc_id: int):
    fav = FavoriteLocation.query.filter_by(id=loc_id, user_id=current_user.id).first()
    if not fav:
        return jsonify({"error": "Favorite location not found."}), 404
    db.session.delete(fav)
    db.session.commit()
    return jsonify({"deleted": True, "id": loc_id})


@properties_bp.route("/api/properties/saved", methods=["GET"])
@login_required
def api_saved_properties():
    items = SavedProperty.query.filter_by(user_id=current_user.id).order_by(SavedProperty.created_at.desc()).all()
    return jsonify({"properties": [p.to_dict() for p in items]})


@properties_bp.route("/api/properties/saved/<int:prop_id>", methods=["DELETE"])
@login_required
def api_delete_saved_property(prop_id: int):
    prop = SavedProperty.query.filter_by(id=prop_id, user_id=current_user.id).first()
    if not prop:
        return jsonify({"error": "Saved property not found."}), 404
    db.session.delete(prop)
    db.session.commit()
    return jsonify({"deleted": True, "id": prop_id})


@properties_bp.route("/api/properties/compare", methods=["POST"])
@limiter.limit("60 per hour")
def api_compare_properties():
    """
    Compare up to 4 properties side-by-side. Each item can supply either a saved prediction_id
    or direct model inputs (exact 11 raw features + optional user-provided monthly_rent & location).
    """
    body = request.get_json(silent=True) or {}
    items = body.get("properties") or []
    if not isinstance(items, list) or len(items) < 2 or len(items) > 4:
        return jsonify({"error": "Provide between 2 and 4 properties to compare."}), 400

    compared = []
    for idx, item in enumerate(items):
        title = (item.get("title") or f"Property {idx + 1}").strip()[:120]
        location_name = (item.get("location_name") or "Not specified").strip()[:160]
        monthly_rent = item.get("monthly_rent")
        amenities_score = item.get("connectivity_index")

        if item.get("prediction_id"):
            pred = db.session.get(Prediction, int(item["prediction_id"]))
            if not pred:
                return jsonify({"error": f"Prediction ID {item['prediction_id']} not found."}), 404
            pdict = pred.to_dict()
            price_inr = pdict["predicted_price_inr"]
            price_usd = pdict["predicted_price_usd"]
            lot_area = float(pdict["lot_area"] or 1)
            bsmt_sf = float(pdict["total_bsmt_sf"] or 0)
            year_built = int(pdict["year_built"] or 2000)
            cond = int(pdict["overall_cond"] or 5)
            bldg_type = pdict["bldg_type"]
            zoning = pdict["ms_zoning"]
            ens_min_inr = pdict["ensemble_min_inr"]
            ens_max_inr = pdict["ensemble_max_inr"]
            cv_pct = round(pdict["ensemble_cv"] * 100, 1)
            title = item.get("title") or pdict["property_title"]
            location_name = item.get("location_name") or pdict.get("location_name") or "Not specified"
            if amenities_score is None and pdict.get("amenities"):
                amenities_score = pdict["amenities"].get("connectivity_index")
        else:
            try:
                res = prediction_service.predict(item)
            except ValueError as exc:
                return jsonify({"error": f"Property {idx + 1}: {exc}"}), 400
            price_inr = res["predicted_price_inr"]
            price_usd = res["predicted_price_usd"]
            inp = res["input_features"]
            lot_area = float(inp["LotArea"])
            bsmt_sf = float(inp["TotalBsmtSF"])
            year_built = int(inp["YearBuilt"])
            cond = int(inp["OverallCond"])
            bldg_type = inp["BldgType"]
            zoning = inp["MSZoning"]
            ens_min_inr = res["ensemble_uncertainty"]["min_inr"]
            ens_max_inr = res["ensemble_uncertainty"]["max_inr"]
            cv_pct = res["ensemble_uncertainty"]["cv_pct"]

        ppsf_lot = round(price_inr / max(lot_area, 1.0), 2)
        emi = calculate_emi(price_inr, down_payment_pct=20.0, annual_interest_rate=8.5, tenure_years=20)

        # Only calculate rental yield if user explicitly provided a real/expected monthly rent
        rental_yield = None
        if monthly_rent not in (None, "", 0, "0"):
            try:
                mr = float(monthly_rent)
                if mr > 0:
                    rental_yield = calculate_rental_yield(price_inr, mr)
            except (TypeError, ValueError):
                pass

        # Transparent deterministic structural suitability score (0-100)
        cond_pts = (cond / 9.0) * 30.0
        age_pts = max(0.0, min(1.0, (year_built - 1940) / 80.0)) * 25.0
        space_pts = min(1.0, bsmt_sf / 2200.0) * 25.0
        agreement_pts = max(0.0, min(1.0, 1.0 - (cv_pct / 40.0))) * 20.0
        suitability_score = round(cond_pts + age_pts + space_pts + agreement_pts, 1)

        compared.append(
            {
                "title": title,
                "location_name": location_name,
                "predicted_price_inr": round(price_inr, 2),
                "predicted_price_usd": round(price_usd, 2),
                "ensemble_min_inr": round(ens_min_inr, 2),
                "ensemble_max_inr": round(ens_max_inr, 2),
                "ensemble_cv_pct": cv_pct,
                "price_per_sqft_lot_inr": ppsf_lot,
                "lot_area": lot_area,
                "total_bsmt_sf": bsmt_sf,
                "year_built": year_built,
                "overall_cond": cond,
                "bldg_type": bldg_type,
                "ms_zoning": zoning,
                "monthly_emi_inr": emi["monthly_emi"],
                "connectivity_index": amenities_score,
                "rental_yield": rental_yield,
                "suitability_score": suitability_score,
            }
        )

    best_value = min(compared, key=lambda x: x["price_per_sqft_lot_inr"])
    best_suitability = max(compared, key=lambda x: x["suitability_score"])

    return jsonify(
        {
            "properties": compared,
            "highlights": {
                "lowest_price_per_sqft": best_value["title"],
                "highest_structural_score": best_suitability["title"],
                "methodology_note": (
                    "Structural Suitability Score (0-100) is transparently derived from Condition (30%), "
                    "Build Vintage (25%), Footprint Area (25%), and Model Tree Agreement (20%). "
                    "Rental yield is computed only when user-supplied monthly rent is entered."
                ),
            },
            "fx": get_usd_to_inr_rate(),
        }
    )
