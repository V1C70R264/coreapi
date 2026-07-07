from django.urls import path
from accounts.views.password_views import (
    PasswordResetRequestView,
    PasswordResetConfirmView,
    PasswordResetValidateView,
    PasswordResetOTPView,
    PasswordResetConfirmOTPView,
)

urlpatterns = [
    path("request/", PasswordResetRequestView.as_view()),
    path("confirm/", PasswordResetConfirmView.as_view()),
    path("validate/", PasswordResetValidateView.as_view()),
    path("otp/request/", PasswordResetOTPView.as_view()),
    path("otp/confirm/", PasswordResetConfirmOTPView.as_view()),
]