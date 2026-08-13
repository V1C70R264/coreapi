import logging
from dataclasses import dataclass
from urllib.parse import unquote

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .email_service import send_html_email

logger = logging.getLogger(__name__)
User = get_user_model()


class ApiPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    """
    Same HMAC mechanism as Django's default, but the hash does **not** include
    ``last_login``.

    Stock ``PasswordResetTokenGenerator`` bakes ``last_login`` into the digest.
    Any login that runs Django's ``update_last_login`` between sending the
    email and submitting the new password will invalidate the link, which is
    easy to hit in real apps and looks like a random "expired" token.

    The password field is still part of the hash, so the link becomes invalid
    as soon as the password changes (including after a successful reset).
    """

    def _make_hash_value(self, user, timestamp):
        email_field = user.get_email_field_name()
        email = getattr(user, email_field, "") or ""
        return f"{user.pk}{user.password}{timestamp}{email}"


# Uses PASSWORD_RESET_TIMEOUT; tied to user password (invalidates after reset).
password_reset_token_generator = ApiPasswordResetTokenGenerator()


@dataclass
class PasswordResetTokenValidationResult:
    is_valid: bool
    user: object | None = None
    error: str | None = None


def get_client_ip(request) -> str:
    """
    Extract client IP in proxy-aware environments.
    """
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def build_frontend_reset_url(uid: str, token: str) -> str:
    """
    Build SPA reset URL: {FRONTEND_URL}/reset-password/{uid}/{token}/
    """
    frontend_base_url = (
        getattr(settings, "FRONTEND_URL", "")
        or getattr(settings, "PASSWORD_RESET_PUBLIC_BASE_URL", "")
        or ""
    ).strip().rstrip("/")
    uid = uid.strip()
    token = token.strip()
    return f"{frontend_base_url}/reset-password/{uid}/{token}/"


def generate_reset_identifiers(user) -> tuple[str, str]:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = password_reset_token_generator.make_token(user)
    return uid, token


def validate_reset_token(uid: str, token: str) -> PasswordResetTokenValidationResult:
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return PasswordResetTokenValidationResult(is_valid=False, error="invalid_uid")

    if not user.is_active:
        return PasswordResetTokenValidationResult(is_valid=False, error="invalid_or_expired_token")

    if not password_reset_token_generator.check_token(user, token):
        return PasswordResetTokenValidationResult(is_valid=False, error="invalid_or_expired_token")

    return PasswordResetTokenValidationResult(is_valid=True, user=user)


def send_password_reset_email(user, reset_url: str) -> bool:
    timeout_seconds = int(getattr(settings, "PASSWORD_RESET_TIMEOUT", 900))
    timeout_minutes = max(1, timeout_seconds // 60)
    subject = "Reset Your Password"
    context = {
        "user": user,
        "reset_url": reset_url,
        "timeout_minutes": timeout_minutes,
        "product_name": "CoreAPI",
    }

    html_body = render_to_string("accounts/emails/password_reset_email.html", context)
    text_body = strip_tags(html_body)
    result = send_html_email(
        subject=subject,
        body_text=text_body,
        body_html=html_body,
        recipient_list=[user.email],
        fail_silently=False,
    )

    if not result.ok:
        logger.error(
            "Failed to send password reset email. user_id=%s email=%s code=%s",
            user.id,
            user.email,
            result.error_code,
        )
        return False

    logger.info("Password reset email sent. user_id=%s email=%s", user.id, user.email)
    return True
