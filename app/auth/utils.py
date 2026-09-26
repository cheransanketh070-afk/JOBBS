import logging
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app, url_for
from flask_mail import Message

from app.extensions import mail

logger = logging.getLogger("jobbs.auth")

VERIFY_SALT = "jobbs-email-verify"
MAX_AGE_SECONDS = 60 * 60 * 24  # 24 hours


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])


def generate_verification_token(email: str) -> str:
    return _serializer().dumps(email, salt=VERIFY_SALT)


def confirm_verification_token(token: str, max_age: int = MAX_AGE_SECONDS):
    try:
        email = _serializer().loads(token, salt=VERIFY_SALT, max_age=max_age)
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"
    return email, None


def send_verification_email(user_email: str, user_name: str):
    token = generate_verification_token(user_email)
    verify_url = url_for("auth.verify_email", token=token, _external=True)

    subject = f"Verify your {current_app.config['SITE_NAME']} account"
    body = (
        f"Hi {user_name},\n\n"
        f"Welcome to {current_app.config['SITE_NAME']}! Please confirm your email "
        f"address by opening this link (valid for 24 hours):\n\n{verify_url}\n\n"
        "If you didn't create this account, you can ignore this email."
    )

    if current_app.config.get("MAIL_ENABLED"):
        try:
            msg = Message(subject=subject, recipients=[user_email], body=body)
            mail.send(msg)
            return
        except Exception as exc:  # noqa: BLE001
            # Covers SMTP auth failures as well as connection timeouts
            # (e.g. a host silently blocking outbound port 587).
            logger.error("Failed to send verification email via SMTP: %s", exc)

    # Fallback for local/dev use when SMTP isn't configured yet:
    logger.warning(
        "MAIL NOT CONFIGURED — verification link for %s: %s", user_email, verify_url
    )
