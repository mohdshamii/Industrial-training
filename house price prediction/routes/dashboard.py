from flask import Blueprint, render_template
from flask_login import login_required, current_user
from database.models import Prediction, SavedProperty, FavoriteLocation
from services.prediction_service import prediction_service
from services.market_service import get_dataset_market_insights, get_usd_to_inr_rate, format_inr

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def index():
    prediction_service.load()
    fx = get_usd_to_inr_rate()
    ds = get_dataset_market_insights()
    total_predictions = Prediction.query.count()
    return render_template(
        "index.html",
        validation_metrics=prediction_service.validation_metrics,
        fx=fx,
        dataset_summary=ds["summary"],
        median_inr_formatted=format_inr(ds["summary"]["median_usd"] * fx["rate"]),
        total_predictions=total_predictions,
    )


@dashboard_bp.route("/dashboard")
@login_required
def user_dashboard():
    prediction_service.load()
    fx = get_usd_to_inr_rate()

    predictions = (
        Prediction.query.filter_by(user_id=current_user.id)
        .order_by(Prediction.created_at.desc())
        .limit(20)
        .all()
    )
    recently_viewed = (
        Prediction.query.filter_by(user_id=current_user.id)
        .order_by(Prediction.viewed_at.desc())
        .limit(6)
        .all()
    )
    saved_properties = (
        SavedProperty.query.filter_by(user_id=current_user.id)
        .order_by(SavedProperty.created_at.desc())
        .all()
    )
    favorite_locations = (
        FavoriteLocation.query.filter_by(user_id=current_user.id)
        .order_by(FavoriteLocation.created_at.desc())
        .all()
    )

    avg_val_inr = (
        sum(p.predicted_price_inr for p in predictions) / len(predictions)
        if predictions
        else 0.0
    )

    return render_template(
        "dashboard.html",
        predictions=predictions,
        recently_viewed=recently_viewed,
        saved_properties=saved_properties,
        favorite_locations=favorite_locations,
        avg_val_inr=avg_val_inr,
        fx=fx,
        format_inr=format_inr,
    )
