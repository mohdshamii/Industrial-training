import math
import time
import threading
from typing import Dict, Any, List, Optional
import requests
from flask import current_app
from services import get_cached_json, set_cached_json, log_api_usage

_nominatim_lock = threading.Lock()
_last_nominatim_call = 0.0

WMO_WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with hail",
    99: "Severe thunderstorm with hail",
}

AMENITY_CATEGORIES = [
    "schools",
    "hospitals",
    "metro_stations",
    "railway_stations",
    "shopping_malls",
    "restaurants",
    "parks",
    "airports",
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two WGS84 coordinates in kilometers."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def _throttle_nominatim():
    """Respect OpenStreetMap Nominatim 1 request/second usage policy."""
    global _last_nominatim_call
    with _nominatim_lock:
        elapsed = time.time() - _last_nominatim_call
        if elapsed < 1.05:
            time.sleep(1.05 - elapsed)
        _last_nominatim_call = time.time()


def geocode_location(query: str, limit: int = 5) -> Dict[str, Any]:
    """Search locations using OpenStreetMap Nominatim with caching & rate-limit compliance."""
    q = (query or "").strip()
    if len(q) < 2:
        return {"results": [], "error": "Enter at least 2 characters to search a location."}

    cache_key = f"nominatim:search:{q.lower()}:{limit}"
    cached = get_cached_json(cache_key)
    if cached:
        log_api_usage("nominatim", "/api/geocode", 200, True, 0.5, q)
        return {**cached, "cached": True}

    t0 = time.perf_counter()
    user_agent = current_app.config.get("NOMINATIM_USER_AGENT", "EstateIQ-AI/1.0")
    ttl = int(current_app.config.get("GEO_CACHE_TTL_SECONDS", 86400))

    try:
        _throttle_nominatim()
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "jsonv2", "addressdetails": 1, "limit": min(max(limit, 1), 8)},
            headers={"User-Agent": user_agent, "Accept-Language": "en"},
            timeout=8,
        )
        latency = (time.perf_counter() - t0) * 1000
        if resp.status_code != 200:
            log_api_usage("nominatim", "/api/geocode", resp.status_code, False, latency, q)
            return {"results": [], "error": f"Geocoding service returned HTTP {resp.status_code}."}

        raw_items = resp.json()
        results = []
        for item in raw_items:
            addr = item.get("address", {})
            city = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("state_district") or ""
            results.append(
                {
                    "name": item.get("name") or q,
                    "display_name": item.get("display_name", q),
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                    "city": city,
                    "state": addr.get("state", ""),
                    "country": addr.get("country", ""),
                    "type": item.get("type", "place"),
                }
            )
        payload = {"results": results, "source": "OpenStreetMap Nominatim"}
        set_cached_json(cache_key, "nominatim", payload, ttl_seconds=ttl)
        log_api_usage("nominatim", "/api/geocode", 200, False, latency, q)
        return {**payload, "cached": False}
    except requests.Timeout:
        log_api_usage("nominatim", "/api/geocode", 504, False, (time.perf_counter() - t0) * 1000, q)
        return {"results": [], "error": "Geocoding request timed out. Please retry shortly."}
    except Exception as exc:
        log_api_usage("nominatim", "/api/geocode", 502, False, (time.perf_counter() - t0) * 1000, str(exc)[:100])
        return {"results": [], "error": "Unable to reach OpenStreetMap Nominatim service right now."}


def _classify_osm_element(tags: Dict[str, Any]) -> Optional[str]:
    amenity = tags.get("amenity", "")
    railway = tags.get("railway", "")
    station = tags.get("station", "")
    shop = tags.get("shop", "")
    leisure = tags.get("leisure", "")
    aeroway = tags.get("aeroway", "")

    if amenity in ("school", "college", "university"):
        return "schools"
    if amenity in ("hospital", "clinic"):
        return "hospitals"
    if railway == "subway_entrance" or station == "subway" or tags.get("subway") == "yes":
        return "metro_stations"
    if railway in ("station", "halt"):
        return "railway_stations"
    if shop in ("mall", "department_store", "supermarket"):
        return "shopping_malls"
    if amenity in ("restaurant", "cafe", "fast_food"):
        return "restaurants"
    if leisure in ("park", "garden"):
        return "parks"
    if aeroway in ("aerodrome", "terminal"):
        return "airports"
    return None


def fetch_nearby_facilities(lat: float, lon: float, radius_m: int = 3000) -> Dict[str, Any]:
    """
    Query Overpass API for 8 real nearby facility categories:
    schools, hospitals, metro_stations, railway_stations, shopping_malls, restaurants, parks, airports.
    """
    radius = min(max(int(radius_m), 500), 8000)
    airport_radius = max(radius, 25000)
    lat_r = round(float(lat), 3)
    lon_r = round(float(lon), 3)
    cache_key = f"overpass:{lat_r}:{lon_r}:{radius}"
    cached = get_cached_json(cache_key)
    if cached:
        log_api_usage("overpass", "/api/nearby", 200, True, 0.5, f"{lat_r},{lon_r}")
        return {**cached, "cached": True}

    query = f"""
    [out:json][timeout:15];
    (
      nwr["amenity"~"^(school|college|university|hospital|clinic|restaurant|cafe)$"](around:{radius},{lat},{lon});
      nwr["railway"~"^(station|halt|subway_entrance)$"](around:{radius},{lat},{lon});
      nwr["station"="subway"](around:{radius},{lat},{lon});
      nwr["shop"~"^(mall|department_store)$"](around:{radius},{lat},{lon});
      nwr["leisure"="park"](around:{radius},{lat},{lon});
      nwr["aeroway"="aerodrome"](around:{airport_radius},{lat},{lon});
    );
    out center 160;
    """

    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    user_agent = current_app.config.get("NOMINATIM_USER_AGENT", "EstateIQ-AI/1.0")
    ttl = int(current_app.config.get("GEO_CACHE_TTL_SECONDS", 86400))
    t0 = time.perf_counter()

    raw_elements = None
    last_err = None
    for url in endpoints:
        try:
            resp = requests.post(
                url,
                data={"data": query},
                headers={"User-Agent": user_agent},
                timeout=14,
            )
            if resp.status_code == 200:
                raw_elements = resp.json().get("elements", [])
                break
            last_err = f"HTTP {resp.status_code}"
        except Exception as exc:
            last_err = str(exc)
            continue

    latency = (time.perf_counter() - t0) * 1000
    if raw_elements is None:
        log_api_usage("overpass", "/api/nearby", 503, False, latency, str(last_err)[:100])
        return {
            "lat": lat,
            "lon": lon,
            "radius_m": radius,
            "categories": {cat: [] for cat in AMENITY_CATEGORIES},
            "counts": {cat: 0 for cat in AMENITY_CATEGORIES},
            "nearest": {},
            "connectivity_index": None,
            "source": "OpenStreetMap Overpass API",
            "error": "Nearby facilities API is temporarily rate-limited or unreachable. Try again shortly.",
            "cached": False,
        }

    categorized: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in AMENITY_CATEGORIES}
    seen_keys = set()

    for el in raw_elements:
        tags = el.get("tags", {})
        cat = _classify_osm_element(tags)
        if not cat:
            continue
        el_lat = el.get("lat") or (el.get("center") or {}).get("lat")
        el_lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if el_lat is None or el_lon is None:
            continue
        name = tags.get("name") or tags.get("name:en") or cat.replace("_", " ").title().rstrip("s")
        dedup_key = (cat, name.lower(), round(float(el_lat), 3), round(float(el_lon), 3))
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        dist = haversine_km(lat, lon, float(el_lat), float(el_lon))
        categorized[cat].append(
            {
                "name": name,
                "category": cat,
                "lat": round(float(el_lat), 6),
                "lon": round(float(el_lon), 6),
                "distance_km": dist,
            }
        )

    counts = {}
    nearest = {}
    for cat in AMENITY_CATEGORIES:
        categorized[cat].sort(key=lambda x: x["distance_km"])
        counts[cat] = len(categorized[cat])
        categorized[cat] = categorized[cat][:12]
        if categorized[cat]:
            nearest[cat] = categorized[cat][0]

    # Transparent, deterministic OSM Amenity Density Index (0-100)
    weights = {
        "schools": (18, 5),
        "hospitals": (18, 3),
        "metro_stations": (16, 2),
        "railway_stations": (10, 2),
        "shopping_malls": (12, 3),
        "restaurants": (10, 8),
        "parks": (10, 4),
        "airports": (6, 1),
    }
    score = 0.0
    for cat, (max_pts, cap) in weights.items():
        score += min(counts[cat] / cap, 1.0) * max_pts
    connectivity_index = round(score, 1)

    payload = {
        "lat": lat,
        "lon": lon,
        "radius_m": radius,
        "airport_radius_m": airport_radius,
        "categories": categorized,
        "counts": counts,
        "total_found": sum(counts.values()),
        "nearest": nearest,
        "connectivity_index": connectivity_index,
        "index_methodology": (
            f"Computed transparently from OpenStreetMap POIs within {radius/1000:.1f} km "
            f"(airports within {airport_radius/1000:.0f} km) across 8 facility categories."
        ),
        "source": "OpenStreetMap Overpass API",
    }
    set_cached_json(cache_key, "overpass", payload, ttl_seconds=ttl)
    log_api_usage("overpass", "/api/nearby", 200, False, latency, f"total={payload['total_found']}")
    return {**payload, "cached": False}


def fetch_weather(lat: float, lon: float) -> Dict[str, Any]:
    """Fetch live current weather and 3-day outlook via Open-Meteo (free, no key)."""
    lat_r = round(float(lat), 2)
    lon_r = round(float(lon), 2)
    cache_key = f"openmeteo:{lat_r}:{lon_r}"
    cached = get_cached_json(cache_key)
    if cached:
        log_api_usage("open_meteo", "/api/weather", 200, True, 0.5, f"{lat_r},{lon_r}")
        return {**cached, "cached": True}

    t0 = time.perf_counter()
    ttl = int(current_app.config.get("WEATHER_CACHE_TTL_SECONDS", 1800))
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "forecast_days": 3,
                "timezone": "auto",
            },
            timeout=6,
        )
        latency = (time.perf_counter() - t0) * 1000
        if resp.status_code != 200:
            log_api_usage("open_meteo", "/api/weather", resp.status_code, False, latency, "http_error")
            return {"error": f"Weather API returned HTTP {resp.status_code}"}

        data = resp.json()
        curr = data.get("current", {})
        daily = data.get("daily", {})
        code = int(curr.get("weather_code", 0))
        forecast = []
        dates = daily.get("time", [])
        for i in range(len(dates)):
            dcode = int((daily.get("weather_code") or [0])[i])
            forecast.append(
                {
                    "date": dates[i],
                    "temp_max_c": (daily.get("temperature_2m_max") or [None])[i],
                    "temp_min_c": (daily.get("temperature_2m_min") or [None])[i],
                    "rain_prob_pct": (daily.get("precipitation_probability_max") or [None])[i],
                    "condition": WMO_WEATHER_CODES.get(dcode, "Variable"),
                }
            )
        payload = {
            "temperature_c": curr.get("temperature_2m"),
            "humidity_pct": curr.get("relative_humidity_2m"),
            "wind_kmh": curr.get("wind_speed_10m"),
            "weather_code": code,
            "condition": WMO_WEATHER_CODES.get(code, "Variable"),
            "forecast": forecast,
            "source": "Open-Meteo Live API",
        }
        set_cached_json(cache_key, "open_meteo", payload, ttl_seconds=ttl)
        log_api_usage("open_meteo", "/api/weather", 200, False, latency, payload["condition"])
        return {**payload, "cached": False}
    except Exception as exc:
        log_api_usage("open_meteo", "/api/weather", 502, False, (time.perf_counter() - t0) * 1000, str(exc)[:100])
        return {"error": "Live weather data unavailable right now."}
