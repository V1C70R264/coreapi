from __future__ import annotations

import logging

from django.contrib.auth.base_user import AbstractBaseUser

from accounts.providers.google_provider import GoogleIdentityProvider
from accounts.utils.oauth_errors import OAuthAccountConflictError

from .token_service import TokenService
from .user_service import UserProvisioningService

logger = logging.getLogger(__name__)


class GoogleAuthService:
    """Orchestrates Google token verification, user provisioning, and JWT issuance."""

    def __init__(
        self,
        *,
        google_provider: GoogleIdentityProvider | None = None,
        users: UserProvisioningService | None = None,
        tokens: TokenService | None = None,
    ) -> None:
        self._google = google_provider or GoogleIdentityProvider()
        self._users = users or UserProvisioningService()
        self._tokens = tokens or TokenService()

    @classmethod
    def default(cls) -> GoogleAuthService:
        return cls()

    def sign_in_with_google(self, *, id_token: str) -> tuple[dict[str, str], AbstractBaseUser]:
        identity = self._google.verify_id_token(id_token)
        try:
            user = self._users.upsert_user_from_google(identity)
        except OAuthAccountConflictError as exc:
            logger.warning('Google sign-in blocked: %s', exc.message)
            raise

        tokens = self._tokens.issue_tokens_for_user(user)
        logger.info('Google sign-in success for user_id=%s', user.pk)
        return tokens, user
