import json
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from database import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # 'user' or 'admin'
    preferred_currency = db.Column(db.String(8), nullable=False, default="INR")
    default_city = db.Column(db.String(120), nullable=True, default="Bengaluru, India")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    predictions = db.relationship("Prediction", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    saved_properties = db.relationship("SavedProperty", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    favorite_locations = db.relationship("FavoriteLocation", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    chat_messages = db.relationship("ChatMessage", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "preferred_currency": self.preferred_currency,
            "default_city": self.default_city,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Prediction(db.Model):
    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    session_token = db.Column(db.String(64), nullable=True, index=True)

    property_title = db.Column(db.String(160), nullable=False, default="Untitled Property")
    location_name = db.Column(db.String(200), nullable=True, default="")
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # Exact model inputs stored as JSON
    input_features_json = db.Column(db.Text, nullable=False)
    bldg_type = db.Column(db.String(32), nullable=True, index=True)
    ms_zoning = db.Column(db.String(32), nullable=True, index=True)
    lot_area = db.Column(db.Float, nullable=True)
    total_bsmt_sf = db.Column(db.Float, nullable=True)
    year_built = db.Column(db.Integer, nullable=True)
    overall_cond = db.Column(db.Integer, nullable=True)

    # Model output & statistically grounded ensemble spread
    predicted_price_usd = db.Column(db.Float, nullable=False)
    predicted_price_inr = db.Column(db.Float, nullable=False)
    exchange_rate_used = db.Column(db.Float, nullable=False)
    exchange_rate_source = db.Column(db.String(64), nullable=False, default="live")

    ensemble_min_usd = db.Column(db.Float, nullable=False)
    ensemble_max_usd = db.Column(db.Float, nullable=False)
    ensemble_std_usd = db.Column(db.Float, nullable=False)
    ensemble_cv = db.Column(db.Float, nullable=False)
    price_per_sqft_inr = db.Column(db.Float, nullable=True)

    factors_json = db.Column(db.Text, nullable=True)
    amenities_json = db.Column(db.Text, nullable=True)
    is_saved = db.Column(db.Boolean, nullable=False, default=False)
    viewed_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    @property
    def input_features(self):
        return json.loads(self.input_features_json) if self.input_features_json else {}

    @property
    def factors(self):
        return json.loads(self.factors_json) if self.factors_json else []

    @property
    def amenities(self):
        return json.loads(self.amenities_json) if self.amenities_json else {}

    def to_dict(self):
        rate = self.exchange_rate_used or 84.5
        return {
            "id": self.id,
            "property_title": self.property_title,
            "location_name": self.location_name or "",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "input_features": self.input_features,
            "bldg_type": self.bldg_type,
            "ms_zoning": self.ms_zoning,
            "lot_area": self.lot_area,
            "total_bsmt_sf": self.total_bsmt_sf,
            "year_built": self.year_built,
            "overall_cond": self.overall_cond,
            "predicted_price_usd": round(self.predicted_price_usd, 2),
            "predicted_price_inr": round(self.predicted_price_inr, 2),
            "exchange_rate_used": round(rate, 4),
            "exchange_rate_source": self.exchange_rate_source,
            "ensemble_min_usd": round(self.ensemble_min_usd, 2),
            "ensemble_max_usd": round(self.ensemble_max_usd, 2),
            "ensemble_min_inr": round(self.ensemble_min_usd * rate, 2),
            "ensemble_max_inr": round(self.ensemble_max_usd * rate, 2),
            "ensemble_std_usd": round(self.ensemble_std_usd, 2),
            "ensemble_std_inr": round(self.ensemble_std_usd * rate, 2),
            "ensemble_cv": round(self.ensemble_cv, 4),
            "price_per_sqft_inr": round(self.price_per_sqft_inr, 2) if self.price_per_sqft_inr else None,
            "factors": self.factors,
            "amenities": self.amenities,
            "is_saved": self.is_saved,
            "viewed_at": self.viewed_at.isoformat() if self.viewed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SavedProperty(db.Model):
    __tablename__ = "saved_properties"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey("predictions.id"), nullable=True)

    title = db.Column(db.String(160), nullable=False)
    location_name = db.Column(db.String(200), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    predicted_price_inr = db.Column(db.Float, nullable=False)
    predicted_price_usd = db.Column(db.Float, nullable=False)
    lot_area = db.Column(db.Float, nullable=True)
    total_bsmt_sf = db.Column(db.Float, nullable=True)
    year_built = db.Column(db.Integer, nullable=True)
    bldg_type = db.Column(db.String(32), nullable=True)
    ms_zoning = db.Column(db.String(32), nullable=True)
    overall_cond = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    viewed_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "prediction_id": self.prediction_id,
            "title": self.title,
            "location_name": self.location_name or "",
            "latitude": self.latitude,
            "longitude": self.longitude,
            "predicted_price_inr": round(self.predicted_price_inr, 2),
            "predicted_price_usd": round(self.predicted_price_usd, 2),
            "lot_area": self.lot_area,
            "total_bsmt_sf": self.total_bsmt_sf,
            "year_built": self.year_built,
            "bldg_type": self.bldg_type,
            "ms_zoning": self.ms_zoning,
            "overall_cond": self.overall_cond,
            "notes": self.notes or "",
            "viewed_at": self.viewed_at.isoformat() if self.viewed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FavoriteLocation(db.Model):
    __tablename__ = "favorite_locations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    location_name = db.Column(db.String(160), nullable=False)
    display_name = db.Column(db.String(300), nullable=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    amenities_summary_json = db.Column(db.Text, nullable=True)
    weather_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "location_name": self.location_name,
            "display_name": self.display_name or self.location_name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "amenities_summary": json.loads(self.amenities_summary_json) if self.amenities_summary_json else {},
            "weather": json.loads(self.weather_json) if self.weather_json else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    session_token = db.Column(db.String(64), nullable=True, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    provider_used = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "provider_used": self.provider_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ApiUsageLog(db.Model):
    __tablename__ = "api_usage_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    service_name = db.Column(db.String(48), nullable=False, index=True)
    endpoint = db.Column(db.String(160), nullable=False)
    status_code = db.Column(db.Integer, nullable=False, default=200)
    cached = db.Column(db.Boolean, nullable=False, default=False)
    latency_ms = db.Column(db.Float, nullable=True)
    meta_text = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)


class ApiCache(db.Model):
    __tablename__ = "api_cache"

    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(255), unique=True, nullable=False, index=True)
    service_name = db.Column(db.String(48), nullable=False, index=True)
    payload_json = db.Column(db.Text, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
