from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    """Provider-agnostic identity payload after server-side token verification."""

    provider: str
    subject: str
    email: str | None
    email_verified: bool
    given_name: str
    family_name: str
    picture_url: str | None = None


@runtime_checkable
class IdentityProvider(Protocol):
    """Contract for OIDC / social IdP token verification (extend per provider)."""

    name: str

    def verify_id_token(self, raw_token: str) -> VerifiedIdentity:
        """Verify a raw ID token and return normalized identity or raise OAuthTokenError."""
        ...
