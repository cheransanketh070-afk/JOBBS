import logging
import os

from flask import Flask, render_template
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix

from app.config import Config
from app.extensions import db, login_manager, csrf, mail, oauth, limiter


def _ensure_sqlite_directory_exists(app):
    """
    If SQLALCHEMY_DATABASE_URI points at a SQLite file (relative or
    absolute), make sure its parent folder exists before SQLAlchemy
    tries to open it — sqlite3 will not create missing directories
    itself, which otherwise surfaces as a confusing
    "unable to open database file" error.
    """
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    prefix = "sqlite:///"
    if not uri.startswith(prefix):
        return
    db_path = uri[len(prefix):]
    if not db_path or db_path == ":memory:":
        return
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.getcwd(), db_path)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    logging.basicConfig(level=logging.INFO)

    # Trust one hop of X-Forwarded-* headers from the platform's reverse
    # proxy (Render/Railway/etc.) so request.is_secure and url_for(..,
    # _external=True) resolve to https instead of causing redirect loops.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # --- extensions ---
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    oauth.init_app(app)
    limiter.init_app(app)

    @limiter.request_filter
    def _exempt_static():
        from flask import request
        return request.path.startswith("/static/")

    # --- security headers (CSP, HSTS, etc.) ---
    csp = {
        "default-src": "'self'",
        "img-src": "'self' data: https:",
        "script-src": ["'self'", "https://accounts.google.com"],
        "style-src": ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        "font-src": ["'self'", "https://fonts.gstatic.com"],
        "frame-src": ["https://accounts.google.com"],
    }
    Talisman(
        app,
        content_security_policy=csp,
        force_https=app.config["SESSION_COOKIE_SECURE"],
        strict_transport_security=True,
        session_cookie_secure=app.config["SESSION_COOKIE_SECURE"],
    )

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- blueprints ---
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # --- context processor: expose site-wide values to templates ---
    @app.context_processor
    def inject_globals():
        return {
            "site_name": app.config["SITE_NAME"],
            "google_analytics_id": app.config.get("GOOGLE_ANALYTICS_ID"),
            "google_site_verification": app.config.get("GOOGLE_SITE_VERIFICATION"),
        }

    # --- error pages ---
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template("errors/429.html"), 429

    with app.app_context():
        _ensure_sqlite_directory_exists(app)
        db.create_all()

    return app
