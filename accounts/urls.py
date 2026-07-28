from django.conf import settings
from django.urls import path
from .views import (
    AvatarView,
    RegisterView,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    PasswordResetValidateView,
    PasswordResetOTPView,
    PasswordResetConfirmOTPView,
    ChangePasswordView,
    GoogleAuthView,
    TokenRefresh,
    ProfileView,
    EmailTestView,
)

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/token/refresh/', TokenRefresh.as_view(), name='token_refresh'),
    
    # Password reset (Django PasswordResetTokenGenerator + email link)
    path('auth/password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path(
        'auth/password-reset-confirm/',
        PasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'auth/password-reset-validate/',
        PasswordResetValidateView.as_view(),
        name='password_reset_validate',
    ),
    
    # Password Reset (Modern - OTP Based)
    path('auth/password-reset/otp/', PasswordResetOTPView.as_view(), name='password_reset_otp'),
    path('auth/password-reset/otp/confirm/', PasswordResetConfirmOTPView.as_view(), name='password_reset_otp_confirm'),
    
    # Change Password (Logged In)
    path('auth/change-password/', ChangePasswordView.as_view(), name='change_password'),
    
    # Profile
    path('users/me/', ProfileView.as_view(), name='profile'),
    path('users/me/avatar/', AvatarView.as_view(), name='avatar'),
    
    # Google Auth
    path('auth/google/', GoogleAuthView.as_view(), name='google_auth'),
]

if getattr(settings, 'ENABLE_EMAIL_TEST_API', False):
    urlpatterns.append(
        path('auth/email/test/', EmailTestView.as_view(), name='email_test'),
    )