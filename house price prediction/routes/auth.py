import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from database import db, limiter
from database.models import User, utcnow

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("20 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.user_dashboard"))

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        default_city = (request.form.get("default_city") or "Bengaluru, India").strip()

        if len(full_name) < 2:
            flash("Please enter your full name (at least 2 characters).", "danger")
            return render_template("register.html")
        if not EMAIL_RE.match(email):
            flash("Please enter a valid email address.", "danger")
            return render_template("register.html")
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return render_template("register.html")
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists. Please sign in.", "warning")
            return redirect(url_for("auth.login"))

        user = User(
            full_name=full_name[:120],
            email=email[:180],
            role="user",
            default_city=default_city[:120] or "Bengaluru, India",
            preferred_currency="INR",
            last_login=utcnow(),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        flash("Welcome to EstateIQ AI. Your account is ready.", "success")
        return redirect(url_for("dashboard.user_dashboard"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("30 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.user_dashboard"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = bool(request.form.get("remember"))

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        user.last_login = utcnow()
        db.session.commit()
        login_user(user, remember=remember)

        next_url = request.args.get("next")
        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)
        return redirect(url_for("dashboard.user_dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out securely.", "info")
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        action = request.form.get("action", "update_profile")
        if action == "update_profile":
            full_name = (request.form.get("full_name") or "").strip()
            default_city = (request.form.get("default_city") or "").strip()
            currency = (request.form.get("preferred_currency") or "INR").upper()
            if len(full_name) < 2:
                flash("Full name must be at least 2 characters.", "danger")
            else:
                current_user.full_name = full_name[:120]
                current_user.default_city = default_city[:120]
                current_user.preferred_currency = currency if currency in ("INR", "USD") else "INR"
                db.session.commit()
                flash("Profile preferences updated.", "success")
        elif action == "change_password":
            curr_pw = request.form.get("current_password") or ""
            new_pw = request.form.get("new_password") or ""
            conf_pw = request.form.get("confirm_password") or ""
            if not current_user.check_password(curr_pw):
                flash("Current password is incorrect.", "danger")
            elif len(new_pw) < 8:
                flash("New password must be at least 8 characters.", "danger")
            elif new_pw != conf_pw:
                flash("New passwords do not match.", "danger")
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash("Password changed successfully.", "success")
        return redirect(url_for("auth.profile"))

    return render_template("profile.html")
