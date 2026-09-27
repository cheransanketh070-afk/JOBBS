import logging
import httpx
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


def _send_via_brevo(user_email: str, user_name: str, subject: str, body: str) -> bool:
    """
    Send via Brevo's transactional email HTTP API. Unlike raw SMTP, this
    goes out over normal HTTPS (port 443), which free Render web services
    do NOT block — SMTP ports 25/465/587 are blocked on Render's free tier,
    which is why plain Gmail SMTP fails there with "Network is unreachable".
    """
    api_key = current_app.config.get("BREVO_API_KEY")
    sender_email = current_app.config.get("BREVO_SENDER_EMAIL") or current_app.config.get("MAIL_USERNAME")
    if not api_key or not sender_email:
        return False

    try:
        resp = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "sender": {"name": current_app.config.get("SITE_NAME", "JOBBS"), "email": sender_email},
                "to": [{"email": user_email, "name": user_name}],
                "subject": subject,
                "textContent": body,
            },
            timeout=15.0,
        )
        if resp.status_code in (200, 201):
            return True
        logger.error("Brevo API rejected the email (HTTP %s): %s", resp.status_code, resp.text[:300])
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Brevo API request failed: %s", exc)
        return False


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

    if _send_via_brevo(user_email, user_name, subject, body):
        return

    if current_app.config.get("MAIL_ENABLED"):
        try:
            msg = Message(subject=subject, recipients=[user_email], body=body)
            mail.send(msg)
            return
        except Exception as exc:  # noqa: BLE001
            # Covers SMTP auth failures as well as connection timeouts/blocks
            # (e.g. a host silently blocking outbound port 587).
            logger.error("Failed to send verification email via SMTP: %s", exc)

    # Fallback for local/dev use, or when no email method is configured:
    logger.warning(
        "MAIL NOT CONFIGURED — verification link for %s: %s", user_email, verify_url
    )
