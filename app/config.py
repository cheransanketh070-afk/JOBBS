import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(basedir, ".env"))


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-change-me")

    SITE_URL = os.environ.get("SITE_URL", "http://localhost:5000")
    SITE_NAME = os.environ.get("SITE_NAME", "JOBBS")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "instance", "jobbs.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Free-tier serverless Postgres (e.g. Neon) suspends its compute after a
    # few idle minutes and silently closes existing connections. pool_pre_ping
    # tests each pooled connection with a cheap query before use and quietly
    # reconnects if it's gone stale, instead of surfacing "SSL connection has
    # been closed unexpectedly" errors to the user.
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = _bool(os.environ.get("MAIL_USE_TLS", "true"), True)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "JOBBS <no-reply@jobbs.local>")
    MAIL_ENABLED = bool(MAIL_USERNAME and MAIL_PASSWORD)

    # Brevo's transactional email API (free tier, HTTPS-based) — the
    # recommended way to send verification emails on Render's free tier,
    # since Render blocks outbound SMTP ports (25/465/587) on free web
    # services entirely. Get a free API key at app.brevo.com (no card).
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
    BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")

    GOOGLE_SITE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "")
    GOOGLE_ANALYTICS_ID = os.environ.get("GOOGLE_ANALYTICS_ID", "")

    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    SCRAPE_MAX_RESULTS_CAP = int(os.environ.get("SCRAPE_MAX_RESULTS_CAP", 50))
    SCRAPE_CONCURRENCY = int(os.environ.get("SCRAPE_CONCURRENCY", 5))

    # Secure session / cookie defaults
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool(os.environ.get("FORCE_HTTPS", "true"), True)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_TIME_LIMIT = None
