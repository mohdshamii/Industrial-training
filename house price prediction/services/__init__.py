import json
from datetime import timedelta
from flask import current_app
from flask_login import current_user
from database import db
from database.models import ApiCache, ApiUsageLog, utcnow


def get_cached_json(cache_key: str):
    """Fetch a non-expired cached JSON payload from SQLite/PostgreSQL."""
    try:
        entry = ApiCache.query.filter_by(cache_key=cache_key).first()
        if entry and entry.expires_at > utcnow():
            return json.loads(entry.payload_json)
        if entry and entry.expires_at <= utcnow():
            db.session.delete(entry)
            db.session.commit()
    except Exception:
        db.session.rollback()
    return None


def set_cached_json(cache_key: str, service_name: str, payload, ttl_seconds: int = 3600):
    """Store a JSON payload in the persistent API cache."""
    try:
        expires_at = utcnow() + timedelta(seconds=ttl_seconds)
        serialized = json.dumps(payload)
        entry = ApiCache.query.filter_by(cache_key=cache_key).first()
        if entry:
            entry.payload_json = serialized
            entry.expires_at = expires_at
            entry.created_at = utcnow()
        else:
            entry = ApiCache(
                cache_key=cache_key,
                service_name=service_name,
                payload_json=serialized,
                expires_at=expires_at,
            )
            db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


def log_api_usage(
    service_name: str,
    endpoint: str,
    status_code: int = 200,
    cached: bool = False,
    latency_ms: float = 0.0,
    meta_text: str = "",
):
    """Persist telemetry for Admin API Usage Monitoring."""
    try:
        uid = current_user.id if getattr(current_user, "is_authenticated", False) else None
        log = ApiUsageLog(
            user_id=uid,
            service_name=service_name,
            endpoint=endpoint[:160],
            status_code=status_code,
            cached=cached,
            latency_ms=round(latency_ms, 2),
            meta_text=(meta_text or "")[:200],
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
        if current_app:
            current_app.logger.debug("Skipped api usage log due to DB state.")
