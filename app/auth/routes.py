from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db, limiter, oauth
from app.models import User
from app.auth.forms import RegisterForm, LoginForm
from app.auth.utils import send_verification_email, confirm_verification_token
from app.data_export import append_user_to_csv

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.record_once
def _setup_google_oauth(state):
    app = state.app
    if app.config.get("GOOGLE_CLIENT_ID") and app.config.get("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name="google",
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


@auth_bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per hour")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("An account with this email already exists. Try logging in instead.", "error")
            return render_template("auth/register.html", form=form)

        user = User(name=form.name.data.strip(), email=email)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        append_user_to_csv(user)
        send_verification_email(user.email, user.name)

        flash("Account created! Check your email to verify your address before logging in.", "success")
        return redirect(url_for("auth.verify_sent"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/verify-sent")
def verify_sent():
    return render_template("auth/verify_sent.html")


@auth_bp.route("/verify/<token>")
def verify_email(token):
    email, error = confirm_verification_token(token)
    if error == "expired":
        flash("That verification link expired. Please register again or request a new one.", "error")
        return redirect(url_for("auth.login"))
    if error == "invalid":
        flash("That verification link is invalid.", "error")
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash("We couldn't find that account.", "error")
        return redirect(url_for("auth.register"))

    if not user.is_verified:
        user.is_verified = True
        db.session.commit()

    flash("Email verified! You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("15 per hour")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(form.password.data):
            flash("Incorrect email or password.", "error")
            return render_template("auth/login.html", form=form)

        if not user.is_verified:
            flash("Please verify your email address before logging in.", "error")
            return render_template("auth/login.html", form=form)

        user.last_login_at = datetime.utcnow()
        db.session.commit()
        login_user(user, remember=form.remember.data)
        return redirect(url_for("main.dashboard"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/google/login")
@limiter.limit("15 per hour")
def google_login():
    if not current_app.config.get("GOOGLE_CLIENT_ID"):
        flash("Google sign-in isn't configured on this server yet.", "error")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    if not current_app.config.get("GOOGLE_CLIENT_ID"):
        return redirect(url_for("auth.login"))

    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo")
    if not userinfo:
        # Fallback for Authlib versions/configs that don't auto-parse the ID token
        resp = oauth.google.get("https://openidconnect.googleapis.com/v1/userinfo", token=token)
        userinfo = resp.json()

    google_id = userinfo["sub"]
    email = userinfo["email"].strip().lower()
    name = userinfo.get("name") or email.split("@")[0]

    user = User.query.filter((User.google_id == google_id) | (User.email == email)).first()

    if user is None:
        user = User(name=name, email=email, google_id=google_id, is_verified=True)
        db.session.add(user)
        db.session.commit()
        append_user_to_csv(user)
    else:
        if not user.google_id:
            user.google_id = google_id
        # Google already verifies the email address on its end.
        user.is_verified = True

    user.last_login_at = datetime.utcnow()
    db.session.commit()

    login_user(user)
    return redirect(url_for("main.dashboard"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("main.index"))
