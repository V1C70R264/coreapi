from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.password_reset_service import (
    build_frontend_reset_url,
    generate_reset_identifiers,
    password_reset_token_generator,
    send_password_reset_email,
    validate_reset_token,
)

User = get_user_model()


class PasswordResetServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user_from_email(
            email="reset@example.com",
            password="Start1234!",
            username="resetuser",
        )

    @override_settings(FRONTEND_URL="https://app.example.com")
    def test_build_frontend_reset_url(self):
        reset_url = build_frontend_reset_url("uidABC", "tokXYZ")
        self.assertEqual(
            reset_url,
            "https://app.example.com/reset-password/uidABC/tokXYZ/",
        )

    def test_validate_reset_token_success(self):
        uid, token = generate_reset_identifiers(self.user)
        result = validate_reset_token(uid, token)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.user.id, self.user.id)

    def test_validate_reset_token_invalid(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        result = validate_reset_token(uid, "invalid-token")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error, "invalid_or_expired_token")

    @override_settings(PASSWORD_RESET_TIMEOUT=1)
    def test_validate_reset_token_expired(self):
        uid, token = generate_reset_identifiers(self.user)
        now = datetime.now()
        with patch.object(password_reset_token_generator, "_now", return_value=now + timedelta(seconds=5)):
            result = validate_reset_token(uid, token)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error, "invalid_or_expired_token")

    def test_validate_reset_token_malformed_uid(self):
        result = validate_reset_token("not-valid-base64!!!", "any-token")
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error, "invalid_uid")

    def test_validate_reset_token_inactive_user(self):
        uid, token = generate_reset_identifiers(self.user)
        self.user.is_active = False
        self.user.save()
        result = validate_reset_token(uid, token)
        self.assertFalse(result.is_valid)
        self.assertEqual(result.error, "invalid_or_expired_token")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_HOST="smtp.gmail.com",
        EMAIL_HOST_USER="sender@example.com",
        EMAIL_HOST_PASSWORD="app-password",
        DEFAULT_FROM_EMAIL="sender@example.com",
        FRONTEND_URL="https://app.example.com",
    )
    def test_send_password_reset_email_uses_dynamic_user_email(self):
        reset_url = build_frontend_reset_url("uid123", "token123")
        sent = send_password_reset_email(self.user, reset_url)
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)
        self.assertEqual(mail.outbox[0].subject, "Reset Your Password")


class PasswordResetAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user_from_email(
            email="apiuser@example.com",
            password="Start1234!",
            username="apiuser",
        )
        self.request_url = reverse("accounts:password_reset")
        self.confirm_url = reverse("accounts:password_reset_confirm")
        self.validate_url = reverse("accounts:password_reset_validate")
        self.login_url = reverse("accounts:login")

    @override_settings(FRONTEND_URL="https://frontend.example.com")
    @patch("accounts.views.password_views.send_password_reset_email", return_value=True)
    def test_request_password_reset_for_existing_user(self, mocked_send):
        response = self.client.post(
            self.request_url, {"email": "apiuser@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "If an account exists, a password reset link has been sent.",
        )
        mocked_send.assert_called_once()
        call_url = mocked_send.call_args[0][1]
        self.assertTrue(call_url.startswith("https://frontend.example.com/reset-password/"))
        self.assertTrue(call_url.endswith("/"))

    @patch("accounts.views.password_views.send_password_reset_email", return_value=True)
    def test_request_password_reset_for_unknown_user_is_enumeration_safe(self, mocked_send):
        response = self.client.post(
            self.request_url, {"email": "unknown@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["message"],
            "If an account exists, a password reset link has been sent.",
        )
        mocked_send.assert_not_called()

    @patch("accounts.views.password_views.send_password_reset_email", return_value=False)
    def test_request_password_reset_handles_email_send_failure(self, _mocked_send):
        response = self.client.post(
            self.request_url, {"email": "apiuser@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)

    @override_settings(FRONTEND_URL="https://frontend.example.com")
    @patch("accounts.views.password_views.send_password_reset_email", return_value=True)
    def test_request_password_reset_skips_inactive_user(self, mocked_send):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(
            self.request_url, {"email": "apiuser@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked_send.assert_not_called()

    @patch("accounts.views.password_views.redis_blacklist.clear_user_tokens")
    def test_confirm_password_reset_success(self, mocked_blacklist_clear):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)

        payload = {"uid": uid, "token": token, "password": "NewStrongPass123!"}
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Password reset successful.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass123!"))
        mocked_blacklist_clear.assert_called_once_with(self.user.id)

        login_resp = self.client.post(
            self.login_url,
            {"email": "apiuser@example.com", "password": "NewStrongPass123!"},
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)

        old_login = self.client.post(
            self.login_url,
            {"email": "apiuser@example.com", "password": "Start1234!"},
            format="json",
        )
        self.assertEqual(old_login.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_password_reset_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        payload = {"uid": uid, "token": "bad-token", "password": "NewStrongPass123!"}
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Token is invalid or expired.")

    @override_settings(PASSWORD_RESET_TIMEOUT=1)
    def test_confirm_password_reset_expired_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        now = datetime.now()
        with patch.object(password_reset_token_generator, "_now", return_value=now + timedelta(seconds=5)):
            response = self.client.post(
                self.confirm_url,
                {"uid": uid, "token": token, "password": "NewStrongPass123!"},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Token is invalid or expired.")

    def test_confirm_password_reset_malformed_uid(self):
        payload = {"uid": "!!!", "token": "x", "password": "NewStrongPass123!"}
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "Token is invalid or expired.")

    def test_confirm_password_reset_weak_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        payload = {"uid": uid, "token": token, "password": "123"}
        response = self.client.post(self.confirm_url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_validate_token_success(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = password_reset_token_generator.make_token(self.user)
        response = self.client.post(
            self.validate_url, {"uid": uid, "token": token}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])

    def test_validate_token_invalid(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.post(
            self.validate_url, {"uid": uid, "token": "bad"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["valid"])
