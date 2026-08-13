from __future__ import annotations

from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser
from rest_framework_simplejwt.tokens import RefreshToken


class TokenService:
    """Centralized JWT issuance (SimpleJWT) for all auth flows."""

    def issue_tokens_for_user(self, user: AbstractBaseUser) -> dict[str, str]:
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }

    def issue_pair_with_claims(self, user: AbstractBaseUser, refresh_extra_claims: dict[str, Any] | None = None) -> dict[str, str]:
        """
        Issue tokens; optional extra claims on refresh token for auditing (use sparingly).

        refresh_extra_claims: merged into refresh.payload after for_user (rare).
        """
        refresh = RefreshToken.for_user(user)
        if refresh_extra_claims:
            for key, value in refresh_extra_claims.items():
                refresh[key] = value
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }
