"""Base contracts for external identity providers.

This module defines the common identity shape and interface
used by all social authentication providers (Google, Apple, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class VerifiedIdentity:
    """
    Normalized, trusted identity claims after IdP token verification.

    This object is provider-agnostic and represents the user identity
    returned by any external identity provider.
    """

    provider: str
    subject: str                 # Stable unique ID from the IdP (e.g. Google's `sub`)
    email: str | None
    email_verified: bool
    given_name: str
    family_name: str
    picture_url: str | None


class IdentityProvider(ABC):
    """
    Abstract contract for all external identity providers.

    Any provider (Google, Apple, Facebook, etc.) must implement
    the verify() method and return a VerifiedIdentity object.
    """

    @abstractmethod
    def verify(self, credential: str) -> VerifiedIdentity:
        """
        Verify an external provider credential/token.

        Args:
            credential:
                The token or authorization credential received
                from the client application.

        Returns:
            VerifiedIdentity:
                Normalized verified user identity.
        """

        raise NotImplementedError