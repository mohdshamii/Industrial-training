import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base configuration for EstateIQ AI."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-estateiq-change-in-production-9f8a7c6b")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{(BASE_DIR / 'instance' / 'estateiq.db').as_posix()}",
    )
    # Render/Heroku PostgreSQL URL compatibility
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # Session & CSRF Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Rate Limiting
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "240 per hour")
    RATELIMIT_HEADERS_ENABLED = True

    # Preserved ML Artifact Paths (kept in workspace root without moving/modifying)
    MODEL_PATH = os.environ.get("MODEL_PATH", str(BASE_DIR / "best_house_price_model.pkl"))
    ENCODER_PATH = os.environ.get("ENCODER_PATH", str(BASE_DIR / "onehot_encoder.pkl"))
    FEATURE_COLUMNS_PATH = os.environ.get("FEATURE_COLUMNS_PATH", str(BASE_DIR / "feature_columns.pkl"))
    DATASET_PATH = os.environ.get("DATASET_PATH", str(BASE_DIR / "HousePricePrediction.xlsx"))
    REPORTS_DIR = os.environ.get("REPORTS_DIR", str(BASE_DIR / "reports"))

    # Public Zero-Key AI Provider (enabled by default, no API key needed)
    ENABLE_PUBLIC_AI = os.environ.get("ENABLE_PUBLIC_AI", "true").lower() == "true"
    PUBLIC_AI_URL = os.environ.get("PUBLIC_AI_URL", "https://text.pollinations.ai/openai").strip()
    PUBLIC_AI_MODEL = os.environ.get("PUBLIC_AI_MODEL", "openai").strip()

    # Optional Free-Tier Personal AI API Keys (never hardcoded; set in .env)
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip()
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
    GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
    OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()
    OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free").strip()

    # External Free API Settings
    NOMINATIM_USER_AGENT = os.environ.get("NOMINATIM_USER_AGENT", "EstateIQ-AI/1.0 (contact@estateiq.local)")
    DEFAULT_USD_TO_INR = float(os.environ.get("DEFAULT_USD_TO_INR", "84.50"))
    FX_CACHE_TTL_SECONDS = int(os.environ.get("FX_CACHE_TTL_SECONDS", "21600"))
    GEO_CACHE_TTL_SECONDS = int(os.environ.get("GEO_CACHE_TTL_SECONDS", "86400"))
    WEATHER_CACHE_TTL_SECONDS = int(os.environ.get("WEATHER_CACHE_TTL_SECONDS", "1800"))

    # Default Admin Seed Credentials (override in .env for production)
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@estateiq.ai")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@EstateIQ2026")
    ADMIN_NAME = os.environ.get("ADMIN_NAME", "EstateIQ Administrator")

    # Upload / Request Limits
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB


class DevelopmentConfig(Config):
    DEBUG = True
    SEND_FILE_MAX_AGE_DEFAULT = 0


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False
    ENABLE_PUBLIC_AI = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
