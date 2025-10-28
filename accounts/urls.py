from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    PasswordResetOTPView,
    PasswordResetConfirmOTPView,
    ChangePasswordView,
    GoogleAuthView,
    TokenRefresh,
)

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/token/refresh/', TokenRefresh.as_view(), name='token_refresh'),
    
    # Password Reset (Legacy - Email Link)
    path('auth/password-reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('auth/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    
    # Password Reset (Modern - OTP Based)
    path('auth/password-reset/otp/', PasswordResetOTPView.as_view(), name='password_reset_otp'),
    path('auth/password-reset/otp/confirm/', PasswordResetConfirmOTPView.as_view(), name='password_reset_otp_confirm'),
    
    # Change Password (Logged In)
    path('auth/change-password/', ChangePasswordView.as_view(), name='change_password'),
    
    # Google Auth
    path('auth/google/', GoogleAuthView.as_view(), name='google_auth'),
]