import time
import threading
import requests
import pandas as pd
import numpy as np
from flask import current_app
from services import get_cached_json, set_cached_json, log_api_usage

_dataset_lock = threading.Lock()
_dataset_insights_cache = None

BLDG_TYPE_LABELS = {
    "1Fam": "Single-Family Detached",
    "2fmCon": "Two-Family Conversion",
    "Duplex": "Duplex",
    "Twnhs": "Townhouse Inside Unit",
    "TwnhsE": "Townhouse End Unit",
}

ZONING_LABELS = {
    "RL": "Residential Low Density",
    "RM": "Residential Medium Density",
    "RH": "Residential High Density",
    "FV": "Floating Village Residential",
    "C (all)": "Commercial Zone",
}

LOT_CONFIG_LABELS = {
    "Inside": "Inside Lot",
    "Corner": "Corner Lot",
    "CulDSac": "Cul-de-Sac",
    "FR2": "Frontage on 2 Sides",
    "FR3": "Frontage on 3 Sides",
}


def get_usd_to_inr_rate() -> dict:
    """
    Retrieve live USD -> INR conversion rate from free no-key APIs with persistent caching
    and a transparent offline fallback. Never fabricates live status.
    """
    cache_key = "fx:USD_INR"
    cached = get_cached_json(cache_key)
    if cached:
        return {**cached, "cached": True}

    default_rate = float(current_app.config.get("DEFAULT_USD_TO_INR", 84.50))
    ttl = int(current_app.config.get("FX_CACHE_TTL_SECONDS", 21600))
    t0 = time.perf_counter()

    providers = [
        ("open.er-api.com", "https://open.er-api.com/v6/latest/USD", lambda d: d.get("rates", {}).get("INR")),
        ("frankfurter.app", "https://api.frankfurter.app/latest?from=USD&to=INR", lambda d: d.get("rates", {}).get("INR")),
    ]

    for provider_name, url, extractor in providers:
        try:
            resp = requests.get(url, timeout=4)
            if resp.status_code == 200:
                rate = extractor(resp.json())
                if rate and float(rate) > 10:
                    payload = {
                        "rate": round(float(rate), 4),
                        "source": provider_name,
                        "is_live": True,
                        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
                        "note": f"Live USD to INR exchange rate via {provider_name}",
                    }
                    set_cached_json(cache_key, "currency", payload, ttl_seconds=ttl)
                    log_api_usage("currency", url, 200, False, (time.perf_counter() - t0) * 1000, provider_name)
                    return {**payload, "cached": False}
        except Exception:
            continue

    log_api_usage("currency", "fallback", 503, False, (time.perf_counter() - t0) * 1000, "offline_fallback")
    return {
        "rate": round(default_rate, 4),
        "source": "configured_fallback",
        "is_live": False,
        "updated_at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "note": "Offline fallback reference rate used (live FX API unreachable)",
        "cached": False,
    }


def format_inr(amount: float) -> str:
    """Format INR cleanly in Indian numbering system with Crore/Lakh summary."""
    if amount is None:
        return "INR 0"
    abs_val = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_val >= 1e7:
        return f"{sign}INR {abs_val / 1e7:.2f} Cr"
    if abs_val >= 1e5:
        return f"{sign}INR {abs_val / 1e5:.2f} L"
    return f"{sign}INR {abs_val:,.0f}"


def get_dataset_market_insights(dataset_path: str = None) -> dict:
    """
    Compute real statistical benchmarks directly from HousePricePrediction.xlsx.
    Uses ONLY actual labeled SalePrice rows (N=1,460) for price distributions so mean-imputed
    rows do not distort market statistics, while transparently reporting total dataset rows.
    """
    global _dataset_insights_cache
    with _dataset_lock:
        if _dataset_insights_cache is not None:
            return _dataset_insights_cache

        path = dataset_path or current_app.config["DATASET_PATH"]
        df = pd.read_excel(path)
        total_rows = int(len(df))
        labeled_df = df.dropna(subset=["SalePrice"]).copy()
        labeled_rows = int(len(labeled_df))
        imputed_rows = total_rows - labeled_rows

        prices = labeled_df["SalePrice"].astype(float)
        summary = {
            "total_records": total_rows,
            "labeled_sale_records": labeled_rows,
            "missing_price_records": imputed_rows,
            "mean_usd": round(float(prices.mean()), 2),
            "median_usd": round(float(prices.median()), 2),
            "min_usd": round(float(prices.min()), 2),
            "max_usd": round(float(prices.max()), 2),
            "p25_usd": round(float(prices.quantile(0.25)), 2),
            "p75_usd": round(float(prices.quantile(0.75)), 2),
            "std_usd": round(float(prices.std()), 2),
            "median_lot_area": round(float(df["LotArea"].median()), 1),
            "median_bsmt_sf": round(float(df["TotalBsmtSF"].dropna().median()), 1),
            "median_year_built": int(df["YearBuilt"].median()),
            "data_source_disclaimer": (
                "Derived directly from the project's historical HousePricePrediction.xlsx training dataset "
                f"({labeled_rows:,} actual recorded sales; {imputed_rows:,} rows without recorded SalePrice "
                "excluded from price benchmarks). Not live property listings."
            ),
        }

        # Building Type Breakdown
        by_bldg = []
        for bldg, grp in labeled_df.groupby("BldgType"):
            by_bldg.append(
                {
                    "code": str(bldg),
                    "label": BLDG_TYPE_LABELS.get(str(bldg), str(bldg)),
                    "count": int(len(grp)),
                    "median_usd": round(float(grp["SalePrice"].median()), 2),
                    "mean_usd": round(float(grp["SalePrice"].mean()), 2),
                }
            )
        by_bldg.sort(key=lambda x: x["median_usd"], reverse=True)

        # Zoning Breakdown
        by_zoning = []
        for zone, grp in labeled_df.groupby("MSZoning"):
            by_zoning.append(
                {
                    "code": str(zone),
                    "label": ZONING_LABELS.get(str(zone), str(zone)),
                    "count": int(len(grp)),
                    "median_usd": round(float(grp["SalePrice"].median()), 2),
                    "mean_usd": round(float(grp["SalePrice"].mean()), 2),
                }
            )
        by_zoning.sort(key=lambda x: x["median_usd"], reverse=True)

        # Lot Config Breakdown
        by_lot = []
        for cfg, grp in labeled_df.groupby("LotConfig"):
            by_lot.append(
                {
                    "code": str(cfg),
                    "label": LOT_CONFIG_LABELS.get(str(cfg), str(cfg)),
                    "count": int(len(grp)),
                    "median_usd": round(float(grp["SalePrice"].median()), 2),
                }
            )
        by_lot.sort(key=lambda x: x["median_usd"], reverse=True)

        # Construction Decade Trend
        labeled_df["Decade"] = (labeled_df["YearBuilt"] // 10) * 10
        by_decade = []
        for dec, grp in labeled_df.groupby("Decade"):
            if len(grp) >= 5:
                by_decade.append(
                    {
                        "decade": f"{int(dec)}s",
                        "count": int(len(grp)),
                        "median_usd": round(float(grp["SalePrice"].median()), 2),
                    }
                )
        by_decade.sort(key=lambda x: x["decade"])

        # Overall Condition vs Median SalePrice
        by_cond = []
        for cond, grp in labeled_df.groupby("OverallCond"):
            by_cond.append(
                {
                    "condition": int(cond),
                    "count": int(len(grp)),
                    "median_usd": round(float(grp["SalePrice"].median()), 2),
                }
            )
        by_cond.sort(key=lambda x: x["condition"])

        # Price Distribution Histogram (10 buckets)
        counts, bin_edges = np.histogram(prices, bins=10)
        histogram = [
            {
                "range_label": f"${int(bin_edges[i]/1000)}k-${int(bin_edges[i+1]/1000)}k",
                "min_usd": round(float(bin_edges[i]), 0),
                "max_usd": round(float(bin_edges[i + 1]), 0),
                "count": int(counts[i]),
            }
            for i in range(len(counts))
        ]

        # Numeric feature correlations with SalePrice
        num_cols = ["MSSubClass", "LotArea", "OverallCond", "YearBuilt", "YearRemodAdd", "BsmtFinSF2", "TotalBsmtSF"]
        correlations = []
        for col in num_cols:
            corr = labeled_df[col].corr(labeled_df["SalePrice"])
            if pd.notna(corr):
                correlations.append({"feature": col, "correlation": round(float(corr), 4)})
        correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        _dataset_insights_cache = {
            "summary": summary,
            "by_bldg_type": by_bldg,
            "by_zoning": by_zoning,
            "by_lot_config": by_lot,
            "by_decade": by_decade,
            "by_condition": by_cond,
            "histogram": histogram,
            "correlations": correlations,
            "labeled_prices_sorted": sorted(prices.tolist()),
        }
        return _dataset_insights_cache
