from __future__ import annotations

from unittest.mock import patch

import jwt
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from accounts.views.auth_views import GoogleAuthView


class GoogleAuthApiTests(TestCase):
    def setUp(self) -> None:
        self._throttle_patcher = patch.object(GoogleAuthView, 'get_throttles', return_value=[])
        self._throttle_patcher.start()
        self.addCleanup(self._throttle_patcher.stop)

        self.client = APIClient()
        self.url = reverse('accounts:google_auth')
        self.audience = 'test-web-client.apps.googleusercontent.com'

    def _id_token_payload(
        self,
        *,
        sub: str = 'google-sub-abc',
        email: str = 'oauth.user@example.com',
        email_verified: bool | str = True,
    ) -> dict:
        return {
            'iss': 'https://accounts.google.com',
            'sub': sub,
            'email': email,
            'email_verified': email_verified,
            'given_name': 'OAuth',
            'family_name': 'User',
            'aud': self.audience,
        }

    @patch('accounts.providers.google_provider.id_token.verify_oauth2_token')
    def test_success_creates_user_and_returns_jwt_and_profile(self, mock_verify) -> None:
        mock_verify.return_value = self._id_token_payload()
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': 'fake.jwt'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertIn('access', body)
        self.assertIn('refresh', body)
        self.assertIn('user', body)
        self.assertEqual(body['user']['email'], 'oauth.user@example.com')
        self.assertEqual(body['user']['auth_provider'], User.AuthProvider.GOOGLE)
        self.assertTrue(body['user']['email_verified'])

        user = User.objects.get(email='oauth.user@example.com')
        self.assertEqual(user.google_sub, 'google-sub-abc')
        self.assertTrue(user.has_usable_password() is False)

        decoded = jwt.decode(
            body['access'],
            settings.SECRET_KEY,
            algorithms=['HS256'],
        )
        self.assertEqual(int(decoded['user_id']), user.id)

    @patch('accounts.providers.google_provider.id_token.verify_oauth2_token')
    def test_success_logs_in_existing_google_user(self, mock_verify) -> None:
        User.objects.create_user_from_email(
            email='existing@example.com',
            password=None,
            first_name='E',
            last_name='X',
            auth_provider=User.AuthProvider.GOOGLE,
            google_sub='google-sub-existing',
            email_verified=True,
            last_login_provider=User.AuthProvider.GOOGLE,
        )
        mock_verify.return_value = self._id_token_payload(sub='google-sub-existing', email='existing@example.com')
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': 'fake.jwt'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.filter(email='existing@example.com').count(), 1)

    @patch('accounts.providers.google_provider.id_token.verify_oauth2_token')
    def test_links_google_to_password_user_when_email_verified(self, mock_verify) -> None:
        User.objects.create_user(
            username='pwuser',
            email='same@example.com',
            password='TestPassword123!',
        )
        mock_verify.return_value = self._id_token_payload(email='same@example.com', sub='google-sub-link')
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': 'fake.jwt'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user = User.objects.get(email='same@example.com')
        self.assertEqual(user.google_sub, 'google-sub-link')
        self.assertTrue(user.check_password('TestPassword123!'))

    @patch('accounts.providers.google_provider.id_token.verify_oauth2_token')
    def test_conflict_when_email_user_has_different_google_sub(self, mock_verify) -> None:
        User.objects.create_user(
            username='blocked',
            email='blocked@example.com',
            password='TestPassword123!',
            google_sub='other-google-sub',
        )
        mock_verify.return_value = self._id_token_payload(email='blocked@example.com', sub='attacker-sub')
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': 'fake.jwt'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertNotIn('other-google-sub', response.content.decode())

    @patch('accounts.providers.google_provider.id_token.verify_oauth2_token')
    def test_rejects_unverified_google_email(self, mock_verify) -> None:
        mock_verify.return_value = self._id_token_payload(email_verified=False)
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': 'fake.jwt'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('accounts.providers.google_provider.id_token.verify_oauth2_token')
    def test_expired_token_returns_401(self, mock_verify) -> None:
        mock_verify.side_effect = ValueError('Token expired')
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': 'expired.jwt'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('accounts.providers.google_provider.id_token.verify_oauth2_token')
    def test_invalid_issuer_returns_401(self, mock_verify) -> None:
        bad = self._id_token_payload()
        bad['iss'] = 'https://malicious.example/'
        mock_verify.return_value = bad
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': 'fake.jwt'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('accounts.providers.google_provider.id_token.verify_oauth2_token')
    def test_missing_email_returns_401(self, mock_verify) -> None:
        payload = self._id_token_payload()
        del payload['email']
        mock_verify.return_value = payload
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': 'fake.jwt'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('accounts.providers.google_provider.id_token.verify_oauth2_token')
    def test_invalid_token_returns_401(self, mock_verify) -> None:
        mock_verify.side_effect = ValueError('Bad token')
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': 'bad'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[])
    def test_missing_configuration_returns_503(self) -> None:
        response = self.client.post(self.url, {'id_token': 'x'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_missing_id_token_validation_error(self) -> None:
        with override_settings(GOOGLE_OAUTH2_ALLOWED_AUDIENCES=[self.audience]):
            response = self.client.post(self.url, {'id_token': ''}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
