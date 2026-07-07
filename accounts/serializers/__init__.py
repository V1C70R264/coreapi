"""
DRF serializers for ``accounts``.

Split by concern: ``core`` (registration, profile, password flows), ``oauth`` (IdP tokens).
"""

from .core import (
    ChangePasswordSerializer,
    LoginSerializer,
    PasswordResetConfirmOTPSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetOTPSerializer,
    PasswordResetRequestSerializer,
    PasswordResetValidateSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    LogoutSerializer,
    EmailTestSerializer
)
from .oauth import GoogleIdTokenSerializer

__all__ = [
    'ChangePasswordSerializer',
    'GoogleIdTokenSerializer',
    'LoginSerializer',
    'PasswordResetConfirmOTPSerializer',
    'PasswordResetConfirmSerializer',
    'PasswordResetOTPSerializer',
    'PasswordResetRequestSerializer',
    'PasswordResetValidateSerializer',
    'RegisterSerializer',
    'UserProfileSerializer',
]
