import os
import time
from datetime import datetime, timezone
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.graphics.shapes import Drawing, Rect, String
from flask import current_app
from services.market_service import format_inr, get_dataset_market_insights
from services.investment_service import calculate_emi, simulate_appreciation_scenarios
from services.prediction_service import prediction_service, FEATURE_FRIENDLY_NAMES
from services import log_api_usage

DARK_SLATE = colors.HexColor("#090B10")
EMERALD = colors.HexColor("#D46B99")   # Editorial Baby Pink (primary accent)
INDIGO = colors.HexColor("#1D4ED8")    # Royal Blue (section headers)
MUTED = colors.HexColor("#4B5563")     # Neutral Charcoal
LIGHT_BG = colors.HexColor("#F8FAFC")  # Pure Crisp White-Tint
BORDER = colors.HexColor("#CBD5E1")    # Clean Hairline
ROSE = colors.HexColor("#090B10")      # Jet Black (negative factor bars)


def _build_factor_bar_chart(factors, width=480, height=165):
    """Create a clean ReportLab vector chart showing top feature impact factors."""
    drawing = Drawing(width, height)
    top_factors = (factors or [])[:6]
    if not top_factors:
        return drawing

    drawing.add(String(0, height - 12, "Top Feature Impact vs. Dataset Baseline (INR)", fontName="Helvetica-Bold", fontSize=9.5, fillColor=DARK_SLATE))

    max_abs = max((abs(f.get("delta_inr", 0)) for f in top_factors), default=1.0) or 1.0
    center_x = 290
    max_bar = 140
    row_h = 22
    start_y = height - 34

    # Baseline axis line
    drawing.add(Rect(center_x, 12, 1, height - 34, fillColor=BORDER, strokeColor=None))

    for idx, fac in enumerate(top_factors):
        y = start_y - idx * row_h
        label = (fac.get("label") or fac.get("feature", ""))[:28]
        delta = float(fac.get("delta_inr", 0))
        bar_len = max((abs(delta) / max_abs) * max_bar, 2)
        bar_color = EMERALD if delta >= 0 else ROSE

        drawing.add(String(0, y + 3, label, fontName="Helvetica", fontSize=8.5, fillColor=DARK_SLATE))
        if delta >= 0:
            drawing.add(Rect(center_x + 2, y, bar_len, 12, fillColor=bar_color, strokeColor=None))
            drawing.add(String(center_x + bar_len + 6, y + 3, f"+{format_inr(delta)}", fontName="Helvetica-Bold", fontSize=7.8, fillColor=EMERALD))
        else:
            drawing.add(Rect(center_x - bar_len - 2, y, bar_len, 12, fillColor=bar_color, strokeColor=None))
            drawing.add(String(center_x + 6, y + 3, format_inr(delta), fontName="Helvetica-Bold", fontSize=7.8, fillColor=ROSE))

    return drawing


def generate_prediction_pdf(prediction_record) -> str:
    """
    Generate a comprehensive executive PDF valuation report for a Prediction ORM record.
    Returns the absolute file path to the generated PDF.
    """
    t0 = time.perf_counter()
    reports_dir = Path(current_app.config["REPORTS_DIR"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / f"estateiq_valuation_{prediction_record.id}.pdf"

    prediction_service.load()
    vm = prediction_service.validation_metrics
    ds = get_dataset_market_insights()
    pred_dict = prediction_record.to_dict()
    price_inr = pred_dict["predicted_price_inr"]
    price_usd = pred_dict["predicted_price_usd"]
    rate = pred_dict["exchange_rate_used"]

    emi_info = calculate_emi(price_inr, down_payment_pct=20.0, annual_interest_rate=8.5, tenure_years=20)
    app_sim = simulate_appreciation_scenarios(price_inr, horizon_years=10)

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"EstateIQ AI Valuation Report #{prediction_record.id}",
        author="EstateIQ AI Platform",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Heading1"], fontSize=18, textColor=DARK_SLATE, spaceAfter=4)
    sub_style = ParagraphStyle("SubCustom", parent=styles["Normal"], fontSize=9.5, textColor=MUTED, spaceAfter=10)
    sec_style = ParagraphStyle("SecCustom", parent=styles["Heading2"], fontSize=12, textColor=INDIGO, spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("BodyCustom", parent=styles["Normal"], fontSize=9, leading=13, textColor=DARK_SLATE)
    disclaimer_style = ParagraphStyle("DisclaimerCustom", parent=styles["Normal"], fontSize=8, leading=11.5, textColor=MUTED)

    story = []

    # Executive Header
    story.append(Paragraph("ESTATEIQ AI — PROPERTY VALUATION & INVESTMENT REPORT", title_style))
    gen_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(
        Paragraph(
            f"Report ID: EIQ-{prediction_record.id:05d}  |  Generated: {gen_ts}  |  Property: {pred_dict['property_title']}",
            sub_style,
        )
    )
    story.append(HRFlowable(width="100%", thickness=1.5, color=EMERALD, spaceAfter=10))

    # Valuation KPI Summary Table
    kpi_data = [
        ["ESTIMATED VALUE (INR)", "NATIVE MODEL OUTPUT (USD)", "10-TREE ENSEMBLE SPREAD (INR)", "FX RATE USED"],
        [
            format_inr(price_inr),
            f"${price_usd:,.0f}",
            f"{format_inr(pred_dict['ensemble_min_inr'])} - {format_inr(pred_dict['ensemble_max_inr'])}",
            f"1 USD = {rate:.2f} INR\n({pred_dict['exchange_rate_source']})",
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[125, 115, 145, 105])
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK_SLATE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                ("BACKGROUND", (0, 1), (-1, 1), LIGHT_BG),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 1), (0, 1), 12),
                ("TEXTCOLOR", (0, 1), (0, 1), EMERALD),
                ("FONTSIZE", (1, 1), (-1, 1), 9.5),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("PADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(kpi_table)
    story.append(Spacer(1, 8))

    # Section 1: Property Specifications (Actual 11 Model Features)
    story.append(Paragraph("1. Property Specifications (Model Input Features)", sec_style))
    feats = pred_dict["input_features"]
    spec_rows = [["Feature", "Value", "Feature", "Value"]]
    items = [(FEATURE_FRIENDLY_NAMES.get(k, k), str(v)) for k, v in feats.items()]
    if pred_dict.get("location_name"):
        items.append(("Tagged Location", pred_dict["location_name"][:42]))
    for i in range(0, len(items), 2):
        left = items[i]
        right = items[i + 1] if i + 1 < len(items) else ("", "")
        spec_rows.append([left[0], left[1], right[0], right[1]])

    spec_table = Table(spec_rows, colWidths=[135, 110, 135, 110])
    spec_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(spec_table)

    # Section 2: Valuation Factors Chart & Dataset Benchmark
    story.append(Paragraph("2. Valuation Drivers & Dataset Benchmark", sec_style))
    ds_median_inr = ds["summary"]["median_usd"] * rate
    vs_med = ((price_usd - ds["summary"]["median_usd"]) / ds["summary"]["median_usd"]) * 100
    story.append(
        Paragraph(
            f"Compared against the historical dataset median of <b>{format_inr(ds_median_inr)}</b> "
            f"(${ds['summary']['median_usd']:,.0f} across {ds['summary']['labeled_sale_records']:,} recorded sales), "
            f"this property is estimated <b>{abs(vs_med):.1f}% {'above' if vs_med >= 0 else 'below'}</b> the dataset median. "
            f"Tree ensemble standard deviation is {format_inr(pred_dict['ensemble_std_inr'])} "
            f"(CV = {pred_dict['ensemble_cv']*100:.1f}%).",
            body_style,
        )
    )
    story.append(Spacer(1, 6))
    story.append(_build_factor_bar_chart(pred_dict.get("factors")))

    # Section 3: ML Model Transparency
    story.append(Paragraph("3. Machine Learning Model Details & Verified Metrics", sec_style))
    model_rows = [
        ["Model Artifact", "Algorithm", "Trees / Features", "Verified Validation MAPE", "Validation MAE / RMSE"],
        [
            "best_house_price_model.pkl",
            vm.get("algorithm", "RandomForestRegressor"),
            f"{vm.get('n_estimators', 10)} trees / {vm.get('encoded_features', 37)} encoded",
            f"{vm.get('mape_pct', 18.5)}%",
            f"${vm.get('mae_usd', 30749):,.0f} / ${vm.get('rmse_usd', 44608):,.0f}",
        ],
    ]
    model_table = Table(model_rows, colWidths=[115, 105, 95, 85, 90])
    model_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFF6FF")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.8),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(model_table)

    # Section 4: Illustrative Investment Scenarios
    story.append(Paragraph("4. Illustrative Investment & Financing Scenarios (Not Market Forecasts)", sec_style))
    fv = app_sim["final_values"]
    inv_rows = [
        ["Metric (Illustrative Assumptions)", "Calculated Scenario Value"],
        ["Standard Financing (20% Down, 8.5% p.a., 20 Yrs)", f"Monthly EMI: {format_inr(emi_info['monthly_emi'])} | Loan: {format_inr(emi_info['loan_amount'])}"],
        ["Estimated Upfront Cash (20% Down + 6% Stamp Duty)", format_inr(emi_info["upfront_cash_needed"])],
        ["10-Year Scenario: Conservative (4.0% CAGR)", format_inr(fv["conservative"])],
        ["10-Year Scenario: Moderate (7.0% CAGR)", format_inr(fv["moderate"])],
        ["10-Year Scenario: Optimistic (10.5% CAGR)", format_inr(fv["optimistic"])],
    ]
    inv_table = Table(inv_rows, colWidths=[245, 245])
    inv_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), DARK_SLATE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_BG]),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(inv_table)

    # Section 5: Nearby Amenities (if attached)
    amenities = pred_dict.get("amenities") or {}
    if amenities and amenities.get("counts"):
        story.append(Paragraph("5. Nearby Infrastructure Summary (OpenStreetMap Overpass)", sec_style))
        am_rows = [["Facility Category", "Count Found", "Nearest Facility", "Distance"]]
        counts = amenities.get("counts", {})
        nearest = amenities.get("nearest", {})
        for cat, cnt in counts.items():
            near = nearest.get(cat) or {}
            am_rows.append(
                [
                    cat.replace("_", " ").title(),
                    str(cnt),
                    (near.get("name") or "None in radius")[:38],
                    f"{near['distance_km']} km" if "distance_km" in near else "-",
                ]
            )
        am_table = Table(am_rows, colWidths=[125, 70, 215, 80])
        am_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FDF2F8")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                    ("PADDING", (0, 0), (-1, -1), 4.5),
                ]
            )
        )
        story.append(am_table)

    # Section 6: Important Disclaimers
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.6, color=BORDER, spaceAfter=6))
    story.append(Paragraph("IMPORTANT STATISTICAL & LEGAL DISCLAIMERS", ParagraphStyle("DiscHdr", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, textColor=DARK_SLATE, spaceAfter=3)))
    story.append(
        Paragraph(
            "1. This valuation is generated by the preserved RandomForestRegressor model trained on historical Ames Housing records "
            "(HousePricePrediction.xlsx, USD SalePrice) and converted to INR using the stated exchange rate. It is NOT a certified "
            "real estate appraisal or live local market quote.<br/>"
            "2. The 10-tree ensemble spread reflects internal model tree variance; verified out-of-sample MAPE on the original 80/20 split is 18.50%.<br/>"
            "3. All EMI, rental yield, and appreciation projections are purely mathematical scenarios based on stated assumptions and must not be construed as financial or investment advice.",
            disclaimer_style,
        )
    )

    doc.build(story)
    log_api_usage("pdf_report", f"/api/predictions/{prediction_record.id}/report.pdf", 200, False, (time.perf_counter() - t0) * 1000)
    return str(out_path)
