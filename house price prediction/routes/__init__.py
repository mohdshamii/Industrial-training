import secrets
from functools import wraps
from flask import session, abort, jsonify, request
from flask_login import current_user


def get_or_create_session_token() -> str:
    token = session.get("eiq_session_token")
    if not token:
        token = secrets.token_hex(16)
        session["eiq_session_token"] = token
    return token


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Administrator privileges required."}), 403
            abort(403)
        return f(*args, **kwargs)

    return decorated
