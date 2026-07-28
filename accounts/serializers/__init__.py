"""
DRF serializers for ``accounts``.

Split by concern: ``core`` (registration, profile, password flows), ``oauth`` (IdP tokens).
"""

from .core import (
    AvatarRemoveSerializer,
    AvatarUploadSerializer,
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
    'AvatarRemoveSerializer',
    'AvatarUploadSerializer',
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
