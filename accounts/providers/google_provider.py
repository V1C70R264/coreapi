from __future__ import annotations

import logging
from typing import Iterable, Sequence

from django.conf import settings
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token

from ..utils.oauth_errors import OAuthTokenError

from .base import VerifiedIdentity

logger = logging.getLogger(__name__)

_GOOGLE_ISSUERS = frozenset({'https://accounts.google.com', 'accounts.google.com'})


class GoogleIdentityProvider:
    """
    Verifies Google ID tokens using google-auth.

    ``verify_oauth2_token`` validates JWT signature (JWKS), ``aud`` against allowed
    client IDs, ``iss`` for Google accounts, and ``exp``/``iat`` (including clock skew).
    This class adds issuer allow-list and normalizes claims into ``VerifiedIdentity``.
    """

    name = 'google'

    def __init__(self, allowed_audiences: Sequence[str] | None = None) -> None:
        audiences = list(allowed_audiences or getattr(settings, 'GOOGLE_OAUTH2_ALLOWED_AUDIENCES', []) or [])
        self._allowed_audiences: tuple[str, ...] = tuple(audiences)

    def verify_id_token(self, raw_token: str) -> VerifiedIdentity:
        if not raw_token or not str(raw_token).strip():
            raise OAuthTokenError('Missing ID token.', status_code=400)

        if not self._allowed_audiences:
            logger.error('Google OAuth is not configured: no GOOGLE_OAUTH2_ALLOWED_AUDIENCES.')
            raise OAuthTokenError('Google sign-in is not configured.', status_code=503)

        request = google_auth_requests.Request()
        payload = self._verify_with_audiences(raw_token.strip(), request, self._allowed_audiences)

        iss = payload.get('iss')
        if iss not in _GOOGLE_ISSUERS:
            logger.warning('Rejected Google token: invalid issuer.')
            raise OAuthTokenError('Invalid authentication token.')

        email_raw = payload.get('email')
        email_verified = _coerce_truthy(payload.get('email_verified'))
        sub = payload.get('sub')
        if not sub:
            logger.warning('Rejected Google token: missing sub.')
            raise OAuthTokenError('Invalid authentication token.')

        email_clean: str | None = None
        if isinstance(email_raw, str) and email_raw.strip():
            email_clean = email_raw.strip().lower()

        return VerifiedIdentity(
            provider=self.name,
            subject=str(sub),
            email=email_clean,
            email_verified=email_verified,
            given_name=(payload.get('given_name') or '')[:150],
            family_name=(payload.get('family_name') or '')[:150],
            picture_url=payload.get('picture'),
        )

    def _verify_with_audiences(
        self,
        raw_token: str,
        request: google_auth_requests.Request,
        audiences: Iterable[str],
    ) -> dict:
        last_exc: Exception | None = None
        for aud in audiences:
            try:
                return id_token.verify_oauth2_token(raw_token, request, audience=aud)
            except ValueError as exc:
                last_exc = exc
                continue
        logger.info('Google ID token verification failed for all configured audiences.')
        if last_exc is not None:
            logger.debug('Last verify_oauth2_token error: %s', last_exc)
        raise OAuthTokenError('Invalid or expired Google token.')


def _coerce_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {'true', '1', 'yes'}
