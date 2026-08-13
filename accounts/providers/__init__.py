"""
Identity provider integrations (Google, Apple, Facebook, GitHub, …).

Add new modules alongside ``google_provider.py`` (e.g. ``apple_provider.py``) that
implement ``IdentityProvider`` and return ``VerifiedIdentity``, then wire them in a
facade service similar to ``GoogleAuthService``.
"""

from .base import IdentityProvider, VerifiedIdentity
from .google_provider import GoogleIdentityProvider

__all__ = [
    'VerifiedIdentity',
    'IdentityProvider',
    'GoogleIdentityProvider',
]
