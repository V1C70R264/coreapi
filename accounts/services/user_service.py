from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction

from accounts.models import User
from accounts.providers.base import VerifiedIdentity
from accounts.utils.oauth_errors import OAuthAccountConflictError, OAuthTokenError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class UserProvisioningService:
    """
    Maps a verified IdP identity to a Django user.

    Linking strategy (Google):
    - Prefer lookup by stable provider subject (`google_sub`).
    - If none, lookup by email and link when Google's email is verified.
    - Reject if email user already has a different `google_sub` (prevents account hijack).
    """

    def upsert_user_from_google(self, identity: VerifiedIdentity) -> User:
        if identity.provider != 'google':
            raise ValueError('Expected Google identity.')

        if not identity.email_verified:
            logger.info('Rejected Google login: email not verified by Google (sub redacted).')
            raise OAuthTokenError('Google email must be verified to sign in.')

        if not identity.email:
            logger.info('Rejected Google login: missing email in verified token.')
            raise OAuthTokenError('Google account has no email; cannot create an account.')

        with transaction.atomic():
            user = (
                User.objects.select_for_update()
                .filter(google_sub=identity.subject)
                .first()
            )
            if user:
                return self._update_existing_google_user(user, identity)

            existing_by_email = (
                User.objects.select_for_update()
                .filter(email__iexact=identity.email)
                .first()
            )
            if existing_by_email:
                return self._link_google_to_email_user(existing_by_email, identity)

            return self._create_google_only_user(identity)

    def _update_existing_google_user(self, user: User, identity: VerifiedIdentity) -> User:
        user.email_verified = bool(user.email_verified or identity.email_verified)
        user.last_login_provider = User.AuthProvider.GOOGLE
        if identity.given_name and not user.first_name:
            user.first_name = identity.given_name
        if identity.family_name and not user.last_name:
            user.last_name = identity.family_name
        user.save(
            update_fields=[
                'email_verified',
                'last_login_provider',
                'first_name',
                'last_name',
            ]
        )
        return user

    def _link_google_to_email_user(self, user: User, identity: VerifiedIdentity) -> User:
        if user.google_sub and user.google_sub != identity.subject:
            logger.warning(
                'Google linking conflict: email user already has a different google_sub.',
            )
            raise OAuthAccountConflictError('This email is already linked to a different Google account.')

        user.google_sub = identity.subject
        user.email_verified = True
        user.last_login_provider = User.AuthProvider.GOOGLE
        if identity.given_name and not user.first_name:
            user.first_name = identity.given_name
        if identity.family_name and not user.last_name:
            user.last_name = identity.family_name
        user.save(
            update_fields=[
                'google_sub',
                'email_verified',
                'last_login_provider',
                'first_name',
                'last_name',
            ]
        )
        return user

    def _create_google_only_user(self, identity: VerifiedIdentity) -> User:
        user = User.objects.create_user_from_email(
            email=identity.email,
            password=None,
            first_name=identity.given_name or '',
            last_name=identity.family_name or '',
            auth_provider=User.AuthProvider.GOOGLE,
            google_sub=identity.subject,
            email_verified=True,
            last_login_provider=User.AuthProvider.GOOGLE,
        )
        return user
