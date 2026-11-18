from flask import Blueprint, render_template, request, jsonify
from services.investment_service import (
    calculate_emi,
    calculate_rental_yield,
    calculate_roi,
    calculate_loan_affordability,
    calculate_buy_vs_rent,
    simulate_appreciation_scenarios,
)
from services.market_service import get_dataset_market_insights, get_usd_to_inr_rate
from services.prediction_service import prediction_service

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/analytics")
def analytics_page():
    prediction_service.load()
    fx = get_usd_to_inr_rate()
    ds = get_dataset_market_insights()
    return render_template(
        "analytics.html",
        fx=fx,
        dataset_summary=ds["summary"],
        validation_metrics=prediction_service.validation_metrics,
    )


@analytics_bp.route("/api/analytics/emi", methods=["POST"])
def api_emi():
    d = request.get_json(silent=True) or {}
    try:
        res = calculate_emi(
            property_price=float(d.get("property_price", 15000000)),
            down_payment_pct=float(d.get("down_payment_pct", 20)),
            annual_interest_rate=float(d.get("annual_interest_rate", 8.5)),
            tenure_years=int(d.get("tenure_years", 20)),
            stamp_duty_pct=float(d.get("stamp_duty_pct", 6)),
        )
        return jsonify(res)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid EMI parameters: {exc}"}), 400


@analytics_bp.route("/api/analytics/rental-yield", methods=["POST"])
def api_rental_yield():
    d = request.get_json(silent=True) or {}
    try:
        res = calculate_rental_yield(
            property_price=float(d.get("property_price", 15000000)),
            monthly_rent=float(d.get("monthly_rent", 45000)),
            annual_maintenance=float(d.get("annual_maintenance", 36000)),
            annual_property_tax=float(d.get("annual_property_tax", 12000)),
            vacancy_rate_pct=float(d.get("vacancy_rate_pct", 5)),
        )
        return jsonify(res)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid rental yield parameters: {exc}"}), 400


@analytics_bp.route("/api/analytics/roi", methods=["POST"])
def api_roi():
    d = request.get_json(silent=True) or {}
    try:
        res = calculate_roi(
            property_price=float(d.get("property_price", 15000000)),
            down_payment_pct=float(d.get("down_payment_pct", 20)),
            closing_costs_pct=float(d.get("closing_costs_pct", 6)),
            monthly_rent=float(d.get("monthly_rent", 45000)),
            annual_expenses=float(d.get("annual_expenses", 60000)),
            annual_appreciation_pct=float(d.get("annual_appreciation_pct", 6.5)),
            annual_interest_rate=float(d.get("annual_interest_rate", 8.5)),
            tenure_years=int(d.get("tenure_years", 20)),
            holding_years=int(d.get("holding_years", 7)),
        )
        return jsonify(res)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid ROI parameters: {exc}"}), 400


@analytics_bp.route("/api/analytics/affordability", methods=["POST"])
def api_affordability():
    d = request.get_json(silent=True) or {}
    try:
        res = calculate_loan_affordability(
            monthly_income=float(d.get("monthly_income", 250000)),
            existing_monthly_emis=float(d.get("existing_monthly_emis", 15000)),
            max_foir_pct=float(d.get("max_foir_pct", 45)),
            annual_interest_rate=float(d.get("annual_interest_rate", 8.5)),
            tenure_years=int(d.get("tenure_years", 20)),
            available_down_payment=float(d.get("available_down_payment", 2500000)),
        )
        return jsonify(res)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid affordability parameters: {exc}"}), 400


@analytics_bp.route("/api/analytics/buy-vs-rent", methods=["POST"])
def api_buy_vs_rent():
    d = request.get_json(silent=True) or {}
    try:
        res = calculate_buy_vs_rent(
            property_price=float(d.get("property_price", 15000000)),
            monthly_rent=float(d.get("monthly_rent", 40000)),
            down_payment_pct=float(d.get("down_payment_pct", 20)),
            annual_interest_rate=float(d.get("annual_interest_rate", 8.5)),
            tenure_years=int(d.get("tenure_years", 20)),
            annual_appreciation_pct=float(d.get("annual_appreciation_pct", 6.5)),
            annual_rent_increase_pct=float(d.get("annual_rent_increase_pct", 5.0)),
            investment_return_pct=float(d.get("investment_return_pct", 10.0)),
            annual_maintenance_pct=float(d.get("annual_maintenance_pct", 1.0)),
            horizon_years=int(d.get("horizon_years", 15)),
        )
        return jsonify(res)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid Buy vs Rent parameters: {exc}"}), 400


@analytics_bp.route("/api/analytics/appreciation", methods=["POST"])
def api_appreciation():
    d = request.get_json(silent=True) or {}
    try:
        res = simulate_appreciation_scenarios(
            current_value=float(d.get("current_value", 15000000)),
            horizon_years=int(d.get("horizon_years", 10)),
            conservative_pct=float(d.get("conservative_pct", 4.0)),
            moderate_pct=float(d.get("moderate_pct", 7.0)),
            optimistic_pct=float(d.get("optimistic_pct", 10.5)),
        )
        return jsonify(res)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": f"Invalid appreciation parameters: {exc}"}), 400


@analytics_bp.route("/api/market/dataset-insights", methods=["GET"])
def api_dataset_insights():
    ds = get_dataset_market_insights()
    fx = get_usd_to_inr_rate()
    payload = {k: v for k, v in ds.items() if k != "labeled_prices_sorted"}
    payload["fx"] = fx
    return jsonify(payload)


@analytics_bp.route("/api/market/fx", methods=["GET"])
def api_fx():
    return jsonify(get_usd_to_inr_rate())
