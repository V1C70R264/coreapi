"""
Centralized outbound email with SMTP error handling and structured logging.

Use this instead of calling send_mail() directly so failures are logged consistently
and callers can branch on success without swallowing errors silently.
"""
from __future__ import annotations

import logging
import smtplib
import socket
from typing import Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

logger = logging.getLogger(__name__)


class EmailSendResult:
    __slots__ = ("ok", "error_code", "message")

    def __init__(self, ok: bool, error_code: Optional[str] = None, message: Optional[str] = None):
        self.ok = ok
        self.error_code = error_code
        self.message = message


def _smtp_configured() -> bool:
    user = (getattr(settings, "EMAIL_HOST_USER", None) or "").strip()
    password = getattr(settings, "EMAIL_HOST_PASSWORD", None) or ""
    host = (getattr(settings, "EMAIL_HOST", None) or "").strip()
    return bool(host and user and password)


def send_plain_email(
    subject: str,
    body: str,
    recipient_list: list[str],
    *,
    from_email: Optional[str] = None,
    fail_silently: bool = False,
) -> EmailSendResult:
    """
    Send a plain-text email. On failure, logs full exception server-side;
    returned message is safe for clients (no credentials).
    """
    if not recipient_list:
        logger.warning("send_plain_email called with empty recipient_list")
        return EmailSendResult(False, "NO_RECIPIENTS", "No recipients")

    if not _smtp_configured():
        msg = "SMTP is not fully configured (check EMAIL_HOST, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)"
        logger.error(msg)
        if not fail_silently:
            return EmailSendResult(False, "SMTP_NOT_CONFIGURED", msg)
        return EmailSendResult(False, "SMTP_NOT_CONFIGURED", msg)

    from_addr = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER

    try:
        connection = get_connection(fail_silently=fail_silently)
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_addr,
            to=recipient_list,
            connection=connection,
        )
        email.send(fail_silently=fail_silently)
        logger.info("Email sent subject=%r to=%r", subject, recipient_list)
        return EmailSendResult(True)

    except smtplib.SMTPAuthenticationError:
        logger.exception(
            "SMTP authentication failed (check Gmail address + App Password, less secure apps disabled)"
        )
        return EmailSendResult(
            False,
            "SMTP_AUTHENTICATION_ERROR",
            "SMTP authentication failed",
        )
    except smtplib.SMTPRecipientsRefused:
        logger.exception("SMTP recipients refused")
        return EmailSendResult(False, "SMTP_RECIPIENTS_REFUSED", "Recipient address was refused")
    except smtplib.SMTPSenderRefused:
        logger.exception("SMTP sender refused")
        return EmailSendResult(False, "SMTP_SENDER_REFUSED", "Sender address was refused")
    except smtplib.SMTPDataError:
        logger.exception("SMTP data error")
        return EmailSendResult(False, "SMTP_DATA_ERROR", "SMTP rejected message content")
    except smtplib.SMTPException:
        logger.exception("SMTP error")
        return EmailSendResult(False, "SMTP_ERROR", "Mail server error")
    except socket.timeout:
        logger.exception("SMTP connection timeout after %s s", getattr(settings, "EMAIL_TIMEOUT", None))
        return EmailSendResult(False, "SMTP_TIMEOUT", "Connection to mail server timed out")
    except OSError as exc:
        logger.exception("Network/OS error talking to SMTP host: %s", exc)
        return EmailSendResult(False, "SMTP_NETWORK_ERROR", "Could not reach mail server")
    except Exception:
        logger.exception("Unexpected error sending plain email")
        return EmailSendResult(False, "UNEXPECTED_ERROR", "Unexpected error sending email")


def send_html_email(
    subject: str,
    body_text: str,
    body_html: str,
    recipient_list: list[str],
    *,
    from_email: Optional[str] = None,
    fail_silently: bool = False,
) -> EmailSendResult:
    """Send multipart alternative (plain + HTML)."""
    if not recipient_list:
        return EmailSendResult(False, "NO_RECIPIENTS", "No recipients")

    if not _smtp_configured():
        msg = "SMTP is not fully configured"
        logger.error(msg)
        return EmailSendResult(False, "SMTP_NOT_CONFIGURED", msg)

    from_addr = from_email or getattr(settings, "DEFAULT_FROM_EMAIL", None) or settings.EMAIL_HOST_USER

    try:
        connection = get_connection(fail_silently=fail_silently)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=body_text,
            from_email=from_addr,
            to=recipient_list,
            connection=connection,
        )
        msg.attach_alternative(body_html, "text/html")
        msg.send(fail_silently=fail_silently)
        logger.info("HTML email sent subject=%r to=%r", subject, recipient_list)
        return EmailSendResult(True)

    except smtplib.SMTPAuthenticationError:
        logger.exception("SMTP authentication failed")
        return EmailSendResult(False, "SMTP_AUTHENTICATION_ERROR", "SMTP authentication failed")
    except smtplib.SMTPException:
        logger.exception("SMTP error")
        return EmailSendResult(False, "SMTP_ERROR", "Mail server error")
    except socket.timeout:
        logger.exception("SMTP connection timeout")
        return EmailSendResult(False, "SMTP_TIMEOUT", "Connection to mail server timed out")
    except OSError:
        logger.exception("Network/OS error talking to SMTP host")
        return EmailSendResult(False, "SMTP_NETWORK_ERROR", "Could not reach mail server")
    except Exception:
        logger.exception("Unexpected error sending HTML email")
        return EmailSendResult(False, "UNEXPECTED_ERROR", "Unexpected error sending email")


def verify_smtp_connection() -> EmailSendResult:
    """
    Open and close an SMTP connection (no message). Useful for diagnostics.
    """
    if not _smtp_configured():
        return EmailSendResult(False, "SMTP_NOT_CONFIGURED", "SMTP is not fully configured")

    try:
        conn = get_connection()
        conn.open()
        conn.close()
        logger.info("SMTP connection test OK host=%s port=%s", settings.EMAIL_HOST, settings.EMAIL_PORT)
        return EmailSendResult(True)
    except smtplib.SMTPAuthenticationError:
        logger.exception("SMTP authentication failed during connection test")
        return EmailSendResult(False, "SMTP_AUTHENTICATION_ERROR", "SMTP authentication failed")
    except smtplib.SMTPException:
        logger.exception("SMTP error during connection test")
        return EmailSendResult(False, "SMTP_ERROR", "Mail server error")
    except socket.timeout:
        logger.exception("SMTP connection timeout during connection test")
        return EmailSendResult(False, "SMTP_TIMEOUT", "Connection timed out")
    except OSError:
        logger.exception("Network error during SMTP connection test")
        return EmailSendResult(False, "SMTP_NETWORK_ERROR", "Could not reach mail server")
    except Exception:
        logger.exception("Unexpected error during SMTP connection test")
        return EmailSendResult(False, "UNEXPECTED_ERROR", "Unexpected error")
