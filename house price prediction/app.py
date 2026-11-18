import logging
import os
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from config import CONFIG_MAP, BASE_DIR
from database import db, login_manager, csrf, limiter
from database.models import User
from services.prediction_service import prediction_service
from services.market_service import get_usd_to_inr_rate, format_inr


def create_app(config_name: str = None) -> Flask:
    env = config_name or os.environ.get("FLASK_ENV", "development")
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(CONFIG_MAP.get(env, CONFIG_MAP["development"]))

    # Ensure instance and reports directories exist
    (BASE_DIR / "instance").mkdir(parents=True, exist_ok=True)
    Path(app.config["REPORTS_DIR"]).mkdir(parents=True, exist_ok=True)

    # Configure structured logging
    logging.basicConfig(
        level=logging.INFO if not app.config.get("TESTING") else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"
    csrf.init_app(app)
    limiter.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register Blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.prediction import prediction_bp
    from routes.properties import properties_bp
    from routes.analytics import analytics_bp
    from routes.chatbot import chatbot_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(prediction_bp)
    app.register_blueprint(properties_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(admin_bp)

    # Template helpers & global context (with automatic static cache-busting version)
    @app.context_processor
    def inject_globals():
        try:
            fx = get_usd_to_inr_rate()
        except Exception:
            fx = {"rate": app.config.get("DEFAULT_USD_TO_INR", 84.50), "is_live": False, "source": "fallback"}
        css_path = BASE_DIR / "static" / "css" / "style.css"
        asset_v = str(int(css_path.stat().st_mtime)) if css_path.exists() else "1"
        return {
            "app_name": "EstateIQ AI",
            "format_inr": format_inr,
            "global_fx": fx,
            "asset_version": asset_v,
        }

    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    # Error Handlers
    @app.errorhandler(403)
    def forbidden(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Access forbidden. Administrator privileges required."}), 403
        return render_template("error.html", code=403, title="Access Forbidden", message="You do not have permission to view this resource."), 403

    @app.errorhandler(404)
    def not_found(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Requested API endpoint or resource not found."}), 404
        return render_template("error.html", code=404, title="Page Not Found", message="The requested page could not be located on EstateIQ AI."), 404

    @app.errorhandler(429)
    def rate_limited(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Rate limit exceeded. Please wait briefly before retrying."}), 429
        return render_template("error.html", code=429, title="Too Many Requests", message="You have reached the temporary rate limit. Please wait a moment and try again."), 429

    @app.errorhandler(500)
    def server_error(err):
        app.logger.exception("Unhandled server error: %s", err)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error. Please try again."}), 500
        return render_template("error.html", code=500, title="Internal Server Error", message="An unexpected error occurred while processing your request."), 500

    # Health endpoint for deployment monitoring
    @app.route("/health")
    def health_check():
        prediction_service.load()
        return jsonify(
            {
                "status": "ok",
                "service": "EstateIQ AI",
                "model_loaded": prediction_service._loaded,
                "n_estimators": prediction_service.validation_metrics.get("n_estimators"),
            }
        )

    # Create DB tables & seed initial admin account
    with app.app_context():
        db.create_all()
        _seed_admin(app)
        prediction_service.load()

    return app


def _seed_admin(app: Flask):
    admin_email = app.config.get("ADMIN_EMAIL", "admin@estateiq.ai").lower()
    if not User.query.filter_by(email=admin_email).first():
        admin = User(
            full_name=app.config.get("ADMIN_NAME", "EstateIQ Administrator"),
            email=admin_email,
            role="admin",
            preferred_currency="INR",
            default_city="Bengaluru, India",
        )
        admin.set_password(app.config.get("ADMIN_PASSWORD", "Admin@EstateIQ2026"))
        db.session.add(admin)
        db.session.commit()


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=app.config.get("DEBUG", True))
