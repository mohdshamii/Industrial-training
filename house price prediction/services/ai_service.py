import time
from typing import Dict, Any, List, Optional
import requests
from flask import current_app
from services.market_service import format_inr, get_dataset_market_insights, get_usd_to_inr_rate
from services.investment_service import (
    calculate_emi,
    calculate_buy_vs_rent,
    simulate_appreciation_scenarios,
)
from services import log_api_usage

SYSTEM_PROMPT = """You are EstateIQ AI, a senior real estate intelligence advisor and quantitative analyst.
Rules:
1. Never use emojis. Use clean, structured text and concise bullet points.
2. Never fabricate live real estate listings, fake rental yields, or made-up prediction accuracy.
3. Clearly distinguish between: (a) outputs from the user's RandomForestRegressor ML model (verified validation MAPE 18.50%), (b) historical dataset benchmarks from HousePricePrediction.xlsx, and (c) illustrative mathematical scenarios.
4. When user prediction context is provided, reference their actual numbers in INR and USD, tree ensemble spread, and top driving features.
5. Keep answers practical, analytical, and transparent about assumptions."""


def get_provider_status() -> Dict[str, Any]:
    """Report which LLM providers are configured via environment variables (never exposes keys)."""
    gemini = bool(current_app.config.get("GEMINI_API_KEY"))
    groq = bool(current_app.config.get("GROQ_API_KEY"))
    openrouter = bool(current_app.config.get("OPENROUTER_API_KEY"))
    public_ai = bool(current_app.config.get("ENABLE_PUBLIC_AI", True))
    active = "local_analytical_engine"
    if gemini:
        active = f"gemini ({current_app.config.get('GEMINI_MODEL')})"
    elif groq:
        active = f"groq ({current_app.config.get('GROQ_MODEL')})"
    elif openrouter:
        active = f"openrouter ({current_app.config.get('OPENROUTER_MODEL')})"
    elif public_ai:
        active = "Pollinations Public Free AI (No Key)"
    return {
        "active_provider": active,
        "providers": {
            "gemini": {"configured": gemini, "model": current_app.config.get("GEMINI_MODEL")},
            "groq": {"configured": groq, "model": current_app.config.get("GROQ_MODEL")},
            "openrouter": {"configured": openrouter, "model": current_app.config.get("OPENROUTER_MODEL")},
            "public_free_ai": {"configured": public_ai, "model": current_app.config.get("PUBLIC_AI_MODEL", "openai")},
            "local_analytical_engine": {"configured": True, "model": "Quantitative Context Fallback Engine"},
        },
    }


def _call_public_free_ai(prompt: str, context_block: str, history: List[Dict[str, str]]) -> Optional[str]:
    """
    Zero-key public free AI endpoint (Pollinations OpenAI-compatible API).
    Automatically falls back to EstateIQ Local Analytical Engine on timeout or rate limit.
    """
    if not current_app.config.get("ENABLE_PUBLIC_AI", True):
        return None
    url = current_app.config.get("PUBLIC_AI_URL", "https://text.pollinations.ai/openai")
    model = current_app.config.get("PUBLIC_AI_MODEL", "openai")
    t0 = time.perf_counter()

    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\nLive Platform Context:\n{context_block}"}]
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"][:1200]})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={"model": model, "messages": messages},
            timeout=18,
        )
        latency = (time.perf_counter() - t0) * 1000
        log_api_usage("public_ai", url, resp.status_code, False, latency)
        if resp.status_code == 200:
            data = resp.json()
            choices = data.get("choices") or []
            if choices:
                text = (choices[0].get("message", {}).get("content") or "").strip()
                if text:
                    return text
    except Exception:
        log_api_usage("public_ai", url, 503, False, (time.perf_counter() - t0) * 1000, "fallback_triggered")
    return None


def _call_gemini(prompt: str, context_block: str, history: List[Dict[str, str]]) -> Optional[str]:
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        return None
    model = current_app.config.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    t0 = time.perf_counter()

    contents = []
    for msg in history[-6:]:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"][:1500]}]})
    contents.append({"role": "user", "parts": [{"text": f"Context:\n{context_block}\n\nUser Question: {prompt}"}]})

    try:
        resp = requests.post(
            url,
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.4, "maxOutputTokens": 900},
            },
            timeout=15,
        )
        latency = (time.perf_counter() - t0) * 1000
        log_api_usage("gemini", f"gemini:{model}", resp.status_code, False, latency)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates") or []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    return text
    except Exception:
        log_api_usage("gemini", f"gemini:{model}", 503, False, (time.perf_counter() - t0) * 1000, "exception")
    return None


def _call_openai_compatible(
    service_name: str, url: str, api_key: str, model: str, prompt: str, context_block: str, history: List[Dict[str, str]]
) -> Optional[str]:
    if not api_key:
        return None
    t0 = time.perf_counter()
    messages = [{"role": "system", "content": f"{SYSTEM_PROMPT}\n\nLive Platform Context:\n{context_block}"}]
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"][:1500]})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "temperature": 0.4, "max_tokens": 900},
            timeout=15,
        )
        latency = (time.perf_counter() - t0) * 1000
        log_api_usage(service_name, f"{service_name}:{model}", resp.status_code, False, latency)
        if resp.status_code == 200:
            choices = resp.json().get("choices") or []
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
    except Exception:
        log_api_usage(service_name, f"{service_name}:{model}", 503, False, (time.perf_counter() - t0) * 1000, "exception")
    return None


def _local_analytical_fallback(prompt: str, context: Dict[str, Any]) -> str:
    """
    Data-grounded analytical advisor used automatically when free-tier LLM API keys
    are absent or rate-limited. Uses actual ML predictions, dataset metrics, and calculators.
    """
    q = (prompt or "").lower()
    latest = context.get("latest_prediction")
    recent_list = context.get("recent_predictions") or []
    ds = get_dataset_market_insights()
    fx = get_usd_to_inr_rate()
    rate = fx["rate"]
    median_inr = ds["summary"]["median_usd"] * rate

    # 1. Explain latest prediction
    if any(k in q for k in ["explain", "factor", "why", "prediction", "estimate", "result"]):
        if latest:
            factors = latest.get("factors") or []
            top_pos = [f for f in factors if f.get("delta_inr", 0) > 0][:3]
            top_neg = [f for f in factors if f.get("delta_inr", 0) < 0][:2]
            lines = [
                f"**Valuation Breakdown for '{latest['property_title']}'**",
                f"- Estimated Value: **{format_inr(latest['predicted_price_inr'])}** (${latest['predicted_price_usd']:,.0f} USD at {latest['exchange_rate_used']:.2f} INR/USD).",
                f"- 10-Tree Random Forest Ensemble Range: **{format_inr(latest['ensemble_min_inr'])}** to **{format_inr(latest['ensemble_max_inr'])}** (Coefficient of Variation: {latest['ensemble_cv']*100:.1f}%).",
                f"- Historical Dataset Median: {format_inr(median_inr)} (from 1,460 recorded sales in HousePricePrediction.xlsx).",
            ]
            if top_pos:
                lines.append("\n**Key Positive Value Drivers (vs. Dataset Baseline):**")
                for f in top_pos:
                    lines.append(f"- {f['label']} ({f['input_value']}): +{format_inr(f['delta_inr'])} impact (global importance {f['global_importance_pct']}%)")
            if top_neg:
                lines.append("\n**Downward Factors (vs. Dataset Baseline):**")
                for f in top_neg:
                    lines.append(f"- {f['label']} ({f['input_value']}): {format_inr(f['delta_inr'])} impact (global importance {f['global_importance_pct']}%)")
            lines.append("\n*Methodology Note:* Verified validation MAPE of this preserved model is 18.50%. Use the ensemble spread alongside local comparable sales before making an offer.")
            return "\n".join(lines)
        return (
            "You have not run a valuation yet. Open the **Price Valuation** studio, enter your property's "
            "structural specifications (Total Basement Area, Lot Area, Year Built, Zoning, Building Type), "
            "and ask me again to break down every driving factor."
        )

    # 2. Overpriced / Fair Value check
    if any(k in q for k in ["overpriced", "fair", "worth", "asking", "negotiate", "deal"]):
        if latest:
            lo, mid, hi = latest["ensemble_min_inr"], latest["predicted_price_inr"], latest["ensemble_max_inr"]
            return (
                f"**Fair-Value Diagnostic for '{latest['property_title']}'**\n"
                f"- Model Point Estimate: **{format_inr(mid)}**\n"
                f"- 10-Tree Empirical Spread: **{format_inr(lo)}** (lower bound) to **{format_inr(hi)}** (upper bound)\n"
                f"- **How to evaluate an asking price:**\n"
                f"  1. Asking price below {format_inr(lo)}: Potentially attractive relative to structural features — verify title, condition, and micro-location.\n"
                f"  2. Asking price between {format_inr(lo)} and {format_inr(hi)}: Within the model's statistical tree spread.\n"
                f"  3. Asking price above {format_inr(hi)} (+15% above point estimate): Potentially overpriced unless justified by superior micro-location, recent renovations, or local amenities not captured in the 11 model features.\n\n"
                "Note: Because the underlying ML model carries a verified 18.50% validation MAPE and does not include live neighborhood comparables, cross-check on the Location Map and with local recent registrations."
            )
        return (
            "To evaluate whether a property is overpriced, run a valuation in **Price Valuation** first. "
            "Compare the seller's asking price against both our point estimate and the 10-tree Random Forest spread, "
            "plus price-per-sq-ft and nearby infrastructure scores in **Location Map**."
        )

    # 3. Buy vs Rent
    if any(k in q for k in ["buy or rent", "buy vs rent", "renting", "rent or buy"]):
        price_inr = latest["predicted_price_inr"] if latest else median_inr
        assumed_rent = round((price_inr * 0.032) / 12.0, 0)
        bvr = calculate_buy_vs_rent(property_price=price_inr, monthly_rent=assumed_rent, horizon_years=12)
        emi = calculate_emi(property_price=price_inr)
        return (
            f"**Illustrative Buy vs. Rent Scenario (Property Value: {format_inr(price_inr)})**\n"
            f"- Assumptions: 20% down payment, 8.5% home loan for 20 yrs, 6.5% appreciation scenario, "
            f"illustrative rent of {format_inr(assumed_rent)}/mo (3.2% gross yield), 10% alternative investment return over 12 years.\n"
            f"- Estimated Monthly EMI: **{format_inr(emi['monthly_emi'])}/month** (Upfront cash incl. 6% stamp duty: {format_inr(emi['upfront_cash_needed'])}).\n"
            f"- 12-Year Buyer Projected Net Worth: **{format_inr(bvr['final_buyer_net_worth'])}**\n"
            f"- 12-Year Renter + Investor Projected Net Worth: **{format_inr(bvr['final_renter_net_worth'])}**\n"
            f"- Scenario Outcome: **{bvr['recommendation']}** (Break-even year: {bvr['breakeven_year'] or 'Beyond 12 years'}).\n\n"
            "*Disclaimer:* Calculated mathematical scenario based on illustrative assumptions, not a market forecast. "
            "Customize every input inside the **Investment Analytics -> Buy vs Rent** tab."
        )

    # 4. Future Value / Appreciation
    if any(k in q for k in ["future", "appreciation", "5 year", "10 year", "expected value", "roi"]):
        price_inr = latest["predicted_price_inr"] if latest else median_inr
        sim = simulate_appreciation_scenarios(price_inr, horizon_years=10)
        fv = sim["final_values"]
        return (
            f"**10-Year Illustrative Appreciation Scenarios (Starting Value: {format_inr(price_inr)})**\n"
            f"- Conservative (4.0% CAGR): **{format_inr(fv['conservative'])}**\n"
            f"- Moderate (7.0% CAGR): **{format_inr(fv['moderate'])}**\n"
            f"- Optimistic (10.5% CAGR): **{format_inr(fv['optimistic'])}**\n\n"
            "*Important Distinction:* These are mathematical compound-growth scenarios rather than real-time price forecasts. "
            "Actual long-term appreciation depends on transit infrastructure, employment hubs, zoning changes, and interest rate cycles."
        )

    # 5. Compare properties
    if any(k in q for k in ["compare", "comparison", "versus", "vs", "better property"]):
        if len(recent_list) >= 2:
            p1, p2 = recent_list[0], recent_list[1]
            diff = p1["predicted_price_inr"] - p2["predicted_price_inr"]
            cheaper = p2["property_title"] if diff > 0 else p1["property_title"]
            return (
                f"**Quick Comparison of Your Two Most Recent Valuations**\n"
                f"1. **{p1['property_title']}**: {format_inr(p1['predicted_price_inr'])} | Lot {p1['lot_area']:,.0f} sq ft | Basement {p1['total_bsmt_sf']:,.0f} sq ft | Built {p1['year_built']} | Condition {p1['overall_cond']}/9\n"
                f"2. **{p2['property_title']}**: {format_inr(p2['predicted_price_inr'])} | Lot {p2['lot_area']:,.0f} sq ft | Basement {p2['total_bsmt_sf']:,.0f} sq ft | Built {p2['year_built']} | Condition {p2['overall_cond']}/9\n"
                f"- Valuation Spread: **{format_inr(abs(diff))}** ({cheaper} is lower priced).\n"
                f"- Open the **Property Comparison** page to compare up to 4 properties with interactive price-per-sq-ft and structural radar charts."
            )
        return (
            "Save or run at least **2 property predictions** and I can compare them directly here, "
            "or open the **Property Comparison** module to analyze up to 4 properties side-by-side."
        )

    # 6. Best area / Location investment potential
    if any(k in q for k in ["best area", "location", "investment potential", "neighborhood", "where to buy", "zone"]):
        top_zone = ds["by_zoning"][0]
        top_bldg = ds["by_bldg_type"][0]
        return (
            "**Framework for Evaluating High-Potential Locations & Property Types**\n"
            f"- **Historical Dataset Signal:** In the project's training data (N=1,460 recorded sales), "
            f"**{top_zone['label']} ({top_zone['code']})** has the highest median sale price ({format_inr(top_zone['median_usd'] * rate)}), "
            f"and **{top_bldg['label']}** leads building categories ({format_inr(top_bldg['median_usd'] * rate)}).\n"
            "- **Live Micro-Location Due Diligence (Use Our Location Map):**\n"
            "  1. **Transit Proximity:** Look for Metro or Railway stations within 1.5-2.5 km (verified via OpenStreetMap Overpass).\n"
            "  2. **Social Infrastructure:** Balanced presence of schools, hospitals, parks, and retail within 3 km drives end-user liquidity.\n"
            "  3. **Yield vs. Growth Trade-off:** Mature urban cores often provide steadier rental occupancy, while emerging transit corridors can offer higher scenario upside with higher execution risk.\n"
            "  4. **Verification:** Always verify RERA registration, circle rates, and local comparable transactions — EstateIQ never fabricates live local listing prices."
        )

    # Default comprehensive guidance
    extra = ""
    if latest:
        extra = (
            f"\n\n**Active Valuation Context:** '{latest['property_title']}' estimated at "
            f"**{format_inr(latest['predicted_price_inr'])}** (range {format_inr(latest['ensemble_min_inr'])} - {format_inr(latest['ensemble_max_inr'])})."
        )
    return (
        "I am **EstateIQ AI** (running in Local Analytical Mode because no external LLM API key is set in `.env`). "
        "I can answer data-backed questions using your ML predictions and financial engines:\n"
        "- *'Explain my latest prediction results'*\n"
        "- *'Is this property overpriced?'*\n"
        "- *'Should I buy or rent?'*\n"
        "- *'What is the expected future property value over 10 years?'*\n"
        "- *'Compare my two recent properties'*\n"
        "- *'Which location and zoning has better investment potential?'*"
        f"{extra}"
    )


def generate_assistant_reply(
    prompt: str,
    context: Dict[str, Any],
    history: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Modular multi-provider assistant:
    1. Google Gemini API (free tier via GEMINI_API_KEY)
    2. Groq API (free tier via GROQ_API_KEY)
    3. OpenRouter API (free tier via OPENROUTER_API_KEY)
    4. Built-in Local Analytical Engine (graceful fallback when keys are missing or rate-limited)
    """
    context_lines = []
    latest = context.get("latest_prediction")
    if latest:
        context_lines.append(
            f"Latest User Prediction: '{latest['property_title']}' in '{latest.get('location_name') or 'Unspecified'}' -> "
            f"{format_inr(latest['predicted_price_inr'])} (${latest['predicted_price_usd']:,.0f} USD). "
            f"10-Tree Range: {format_inr(latest['ensemble_min_inr'])} to {format_inr(latest['ensemble_max_inr'])} "
            f"(CV={latest['ensemble_cv']*100:.1f}%). Features: {latest['input_features']}."
        )
    recent = context.get("recent_predictions") or []
    if len(recent) > 1:
        context_lines.append("Other Recent Predictions:")
        for p in recent[1:4]:
            context_lines.append(
                f"  - {p['property_title']}: {format_inr(p['predicted_price_inr'])}, Lot {p['lot_area']} sqft, "
                f"Bsmt {p['total_bsmt_sf']} sqft, Built {p['year_built']}, Type {p['bldg_type']}."
            )
    if context.get("favorite_locations"):
        locs = ", ".join(loc["location_name"] for loc in context["favorite_locations"][:4])
        context_lines.append(f"User Favorite Locations: {locs}")
    context_lines.append(
        "Model Details: Preserved RandomForestRegressor (n_estimators=10), 11 raw features (37 one-hot encoded), "
        "verified validation MAPE = 18.50%, trained on HousePricePrediction.xlsx."
    )
    context_block = "\n".join(context_lines)

    # Try Gemini
    if current_app.config.get("GEMINI_API_KEY"):
        reply = _call_gemini(prompt, context_block, history)
        if reply:
            return {"reply": reply, "provider": f"Google Gemini ({current_app.config.get('GEMINI_MODEL')})", "fallback": False}

    # Try Groq
    if current_app.config.get("GROQ_API_KEY"):
        reply = _call_openai_compatible(
            "groq",
            "https://api.groq.com/openai/v1/chat/completions",
            current_app.config.get("GROQ_API_KEY"),
            current_app.config.get("GROQ_MODEL"),
            prompt,
            context_block,
            history,
        )
        if reply:
            return {"reply": reply, "provider": f"Groq ({current_app.config.get('GROQ_MODEL')})", "fallback": False}

    # Try OpenRouter
    if current_app.config.get("OPENROUTER_API_KEY"):
        reply = _call_openai_compatible(
            "openrouter",
            "https://openrouter.ai/api/v1/chat/completions",
            current_app.config.get("OPENROUTER_API_KEY"),
            current_app.config.get("OPENROUTER_MODEL"),
            prompt,
            context_block,
            history,
        )
        if reply:
            return {"reply": reply, "provider": f"OpenRouter ({current_app.config.get('OPENROUTER_MODEL')})", "fallback": False}

    # Try Public Zero-Key AI (works out-of-the-box without personal API keys)
    if current_app.config.get("ENABLE_PUBLIC_AI", True):
        reply = _call_public_free_ai(prompt, context_block, history)
        if reply:
            return {"reply": reply, "provider": "Pollinations Public Free AI (No Key)", "fallback": False}

    # Graceful local analytical fallback
    t0 = time.perf_counter()
    reply = _local_analytical_fallback(prompt, context)
    log_api_usage("ai_fallback", "/api/chat", 200, False, (time.perf_counter() - t0) * 1000, "local_engine")
    return {
        "reply": reply,
        "provider": "EstateIQ Local Analytical Engine",
        "fallback": True,
    }
