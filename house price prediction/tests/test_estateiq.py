import os
import re
from pathlib import Path
import pytest
from app import create_app
from database import db
from database.models import User


@pytest.fixture()
def app():
    app = create_app("testing")
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_health_and_pages(client):
    assert client.get("/health").status_code == 200
    for route in ["/", "/predict", "/compare", "/map", "/analytics", "/assistant", "/auth/login", "/auth/register"]:
        resp = client.get(route)
        assert resp.status_code == 200, f"Route {route} failed with {resp.status_code}"


def test_preserved_ml_model_schema_and_prediction(client):
    schema_resp = client.get("/api/predict/schema")
    assert schema_resp.status_code == 200
    schema = schema_resp.get_json()
    assert schema["validation_metrics"]["mape_pct"] == 18.5
    assert schema["validation_metrics"]["n_estimators"] == 10
    assert schema["validation_metrics"]["encoded_features"] == 37

    payload = {
        "property_title": "Test Indiranagar Villa",
        "location_name": "Indiranagar, Bengaluru",
        "MSSubClass": 60,
        "LotArea": 9500,
        "OverallCond": 6,
        "YearBuilt": 2005,
        "YearRemodAdd": 2008,
        "BsmtFinSF2": 0,
        "TotalBsmtSF": 1200,
        "MSZoning": "RL",
        "LotConfig": "Corner",
        "BldgType": "1Fam",
        "Exterior1st": "VinylSd",
    }
    resp = client.post("/api/predict", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["predicted_price_usd"] > 30000
    assert data["predicted_price_inr"] > 2500000
    assert data["ensemble_uncertainty"]["n_estimators"] == 10
    assert data["ensemble_uncertainty"]["min_inr"] <= data["predicted_price_inr"] <= data["ensemble_uncertainty"]["max_inr"]
    assert len(data["factors"]) == 11

    # Verify PDF report generation for this prediction
    pdf_resp = client.get(f"/api/predictions/{data['id']}/report.pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.mimetype == "application/pdf"
    assert pdf_resp.data[:5] == b"%PDF-"
    assert len(pdf_resp.data) > 3000


def test_prediction_input_validation(client):
    bad_payload = {
        "MSSubClass": 60,
        "LotArea": 5000,
        "OverallCond": 5,
        "YearBuilt": 2000,
        "YearRemodAdd": 2000,
        "BsmtFinSF2": 2000,
        "TotalBsmtSF": 500,  # invalid: BsmtFinSF2 > TotalBsmtSF
        "MSZoning": "RL",
        "LotConfig": "Inside",
        "BldgType": "1Fam",
        "Exterior1st": "VinylSd",
    }
    resp = client.post("/api/predict", json=bad_payload)
    assert resp.status_code == 400

    bad_cat = dict(bad_payload, BsmtFinSF2=0, MSZoning="INVALID_ZONE")
    resp2 = client.post("/api/predict", json=bad_cat)
    assert resp2.status_code == 400


def test_comparison_engine_api(client):
    p1 = {
        "title": "Home A",
        "MSSubClass": 60, "LotArea": 10000, "OverallCond": 7, "YearBuilt": 2006,
        "YearRemodAdd": 2008, "BsmtFinSF2": 0, "TotalBsmtSF": 1300,
        "MSZoning": "RL", "LotConfig": "Corner", "BldgType": "1Fam", "Exterior1st": "VinylSd",
        "monthly_rent": 50000,
    }
    p2 = {
        "title": "Home B",
        "MSSubClass": 20, "LotArea": 7500, "OverallCond": 5, "YearBuilt": 1985,
        "YearRemodAdd": 1995, "BsmtFinSF2": 0, "TotalBsmtSF": 900,
        "MSZoning": "RM", "LotConfig": "Inside", "BldgType": "TwnhsE", "Exterior1st": "MetalSd",
    }
    resp = client.post("/api/properties/compare", json={"properties": [p1, p2]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["properties"]) == 2
    assert data["properties"][0]["rental_yield"] is not None
    assert data["properties"][1]["rental_yield"] is None

    # Reject invalid counts
    assert client.post("/api/properties/compare", json={"properties": [p1]}).status_code == 400


def test_investment_analytics_and_market_apis(client):
    assert client.post("/api/analytics/emi", json={"property_price": 12000000}).status_code == 200
    assert client.post("/api/analytics/rental-yield", json={"property_price": 12000000, "monthly_rent": 40000}).status_code == 200
    assert client.post("/api/analytics/roi", json={"property_price": 12000000, "monthly_rent": 40000}).status_code == 200
    assert client.post("/api/analytics/affordability", json={"monthly_income": 200000}).status_code == 200
    bvr = client.post("/api/analytics/buy-vs-rent", json={"property_price": 12000000, "monthly_rent": 38000}).get_json()
    assert len(bvr["timeline"]) == 15
    app_sim = client.post("/api/analytics/appreciation", json={"current_value": 12000000, "horizon_years": 10}).get_json()
    assert app_sim["final_values"]["optimistic"] > app_sim["final_values"]["conservative"]

    ds = client.get("/api/market/dataset-insights").get_json()
    assert ds["summary"]["labeled_sale_records"] == 1460
    assert len(ds["by_bldg_type"]) == 5


def test_ai_assistant_contextual_fallback(client):
    # Create a prediction first so assistant has context
    client.post(
        "/api/predict",
        json={
            "property_title": "Context Test Home",
            "MSSubClass": 60, "LotArea": 9800, "OverallCond": 7, "YearBuilt": 2007,
            "YearRemodAdd": 2008, "BsmtFinSF2": 0, "TotalBsmtSF": 1400,
            "MSZoning": "RL", "LotConfig": "Inside", "BldgType": "1Fam", "Exterior1st": "VinylSd",
        },
    )
    resp = client.post("/api/chat", json={"message": "Explain my latest prediction results"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert "Context Test Home" in data["reply"]
    assert client.get("/api/chat/history").status_code == 200
    assert client.delete("/api/chat/history").status_code == 200


def test_auth_and_admin_rbac(client, app):
    # Register standard user
    reg = client.post(
        "/auth/register",
        data={
            "full_name": "Priya Verma",
            "email": "priya@example.com",
            "default_city": "Pune, India",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
        },
        follow_redirects=True,
    )
    assert reg.status_code == 200
    assert b"Priya Verma" in reg.data

    # Standard user MUST be blocked from admin routes
    assert client.get("/admin").status_code == 403
    assert client.get("/api/admin/stats").status_code == 403

    # Sign out and sign in as seeded admin
    client.post("/auth/logout")
    login = client.post(
        "/auth/login",
        data={
            "email": app.config["ADMIN_EMAIL"],
            "password": app.config["ADMIN_PASSWORD"],
        },
        follow_redirects=True,
    )
    assert login.status_code == 200
    assert client.get("/admin").status_code == 200
    stats_resp = client.get("/api/admin/stats")
    assert stats_resp.status_code == 200
    assert stats_resp.get_json()["totals"]["users"] >= 2


def test_no_emojis_in_estateiq_source_files():
    """Verify the strict 'no emojis, SVGs only' requirement across all new platform files."""
    root = Path(__file__).resolve().parent.parent
    emoji_re = re.compile(
        "["
        "\U0001F300-\U0001F9FF"
        "\U0001FA00-\U0001FAFF"
        "\U00002600-\U000027BF"
        "]+",
        flags=re.UNICODE,
    )
    scan_dirs = ["templates", "static", "routes", "services", "database"]
    offenders = []
    for d in scan_dirs:
        for path in (root / d).rglob("*"):
            if path.is_file() and path.suffix in {".html", ".css", ".js", ".py"}:
                content = path.read_text(encoding="utf-8", errors="ignore")
                if emoji_re.search(content):
                    offenders.append(str(path))
    assert offenders == [], f"Found disallowed emojis in: {offenders}"


def test_all_svgs_have_explicit_dimensions():
    """Ensure every SVG icon in templates and JS has explicit width & height so it can never render full-screen."""
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for folder in ["templates", "static/js"]:
        for path in (root / folder).rglob("*"):
            if path.is_file() and path.suffix in {".html", ".js"}:
                content = path.read_text(encoding="utf-8", errors="ignore")
                for tag in re.findall(r"<svg[^>]*>", content):
                    if "width=" not in tag or "height=" not in tag:
                        offenders.append(f"{path.name}: {tag[:80]}")
    assert offenders == [], f"Found unsized SVG tags: {offenders}"
