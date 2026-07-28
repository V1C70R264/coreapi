"""API views split by area; import from ``accounts.views`` for URLConf compatibility."""

from .auth_views import (
    GoogleAuthView,
    LoginView,
    LogoutView,
    RegisterView,
    TokenRefresh,
)
from .password_views import (
    PasswordResetConfirmOTPView,
    PasswordResetConfirmView,
    PasswordResetOTPView,
    PasswordResetRequestView,
    PasswordResetValidateView,
)
from .profile_views import AvatarView, ChangePasswordView, EmailTestView, ProfileView

__all__ = [
    'AvatarView',
    'ChangePasswordView',
    'EmailTestView',
    'GoogleAuthView',
    'LoginView',
    'LogoutView',
    'PasswordResetConfirmOTPView',
    'PasswordResetConfirmView',
    'PasswordResetOTPView',
    'PasswordResetRequestView',
    'PasswordResetValidateView',
    'ProfileView',
    'RegisterView',
    'TokenRefresh',
]
