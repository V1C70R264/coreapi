import logging
from drf_spectacular.utils import extend_schema
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView

from ..otp_reset import otp_reset
from ..password_reset_service import (
    build_frontend_reset_url,
    generate_reset_identifiers,
    get_client_ip,
    send_password_reset_email,
    validate_reset_token,
)
from ..redis_blacklist import redis_blacklist
from ..secure_reset import secure_reset
from ..serializers import (
    PasswordResetConfirmOTPSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetOTPSerializer,
    PasswordResetRequestSerializer,
    PasswordResetValidateSerializer,
)

logger = logging.getLogger(__name__)

User = get_user_model()

_PASSWORD_RESET_REQUEST_MESSAGE = (
    "If an account exists, a password reset link has been sent."
)
_INVALID_RESET_TOKEN_MESSAGE = "Token is invalid or expired."

@extend_schema(
    tags=["Password Management"],
    summary="Request Password Reset",
    description="Send password reset email.",
    request=PasswordResetRequestSerializer,
)
class PasswordResetRequestView(GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    """
    Enumeration-safe password reset request.

    Uses ``PasswordResetTokenGenerator`` and emails a link:
    ``{FRONTEND_URL}/reset-password/{uid}/{token}/``
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset_request"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        ip_address = get_client_ip(request)
        generic_response = {"message": _PASSWORD_RESET_REQUEST_MESSAGE}

        rate_limit_ok, rate_limit_msg = secure_reset.check_rate_limit(email, ip_address)
        if not rate_limit_ok:
            secure_reset.log_reset_attempt(email, ip_address, "RATE_LIMIT_EXCEEDED", False)
            return Response(
                {"detail": rate_limit_msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        secure_reset.increment_rate_limit(email)

        try:
            user = User.objects.filter(email=email, is_active=True).first()
        except Exception:
            logger.exception(
                "password_reset_request: failed to resolve user. email=%s ip=%s",
                email,
                ip_address,
            )
            secure_reset.log_reset_attempt(email, ip_address, "RESET_REQUEST_DB_ERROR", False)
            return Response(generic_response, status=status.HTTP_200_OK)

        if not user:
            secure_reset.log_reset_attempt(email, ip_address, "RESET_REQUEST", False)
            return Response(generic_response, status=status.HTTP_200_OK)

        try:
            uid, token = generate_reset_identifiers(user)
            reset_url = build_frontend_reset_url(uid, token)
        except Exception:
            logger.exception(
                "password_reset_request: failed to build identifiers. user_id=%s ip=%s",
                getattr(user, "id", None),
                ip_address,
            )
            secure_reset.log_reset_attempt(email, ip_address, "RESET_TOKEN_BUILD_FAILED", False)
            return Response(generic_response, status=status.HTTP_200_OK)

        if not reset_url.startswith("http"):
            logger.error(
                "FRONTEND_URL is missing or not absolute; cannot build reset URL. user_id=%s",
                user.id,
            )
            secure_reset.log_reset_attempt(email, ip_address, "RESET_URL_BUILD_FAILED", False)
            return Response(generic_response, status=status.HTTP_200_OK)

        try:
            sent = send_password_reset_email(user, reset_url)
        except Exception:
            logger.exception(
                "password_reset_request: unexpected mail error. user_id=%s email=%s",
                user.id,
                user.email,
            )
            secure_reset.log_reset_attempt(email, ip_address, "RESET_EMAIL_FAILED", False)
            return Response(generic_response, status=status.HTTP_200_OK)

        if not sent:
            secure_reset.log_reset_attempt(email, ip_address, "RESET_EMAIL_FAILED", False)
            return Response(generic_response, status=status.HTTP_200_OK)

        secure_reset.log_reset_attempt(email, ip_address, "RESET_REQUEST", True)
        return Response(generic_response, status=status.HTTP_200_OK)

@extend_schema(
    tags=["Password Management"],
    summary="Confirm Password Reset",
    description="Reset password using uid and token.",
    request=PasswordResetConfirmSerializer,
)
class PasswordResetConfirmView(GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset_confirm"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["password"]
        ip_address = get_client_ip(request)

        validation = validate_reset_token(uid, token)
        if not validation.is_valid or not validation.user:
            secure_reset.log_reset_attempt(
                "unknown", ip_address, "INVALID_OR_EXPIRED_TOKEN", False
            )
            return Response(
                {"error": _INVALID_RESET_TOKEN_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = validation.user
        try:
            validate_password(new_password, user)
        except DjangoValidationError as exc:
            raise ValidationError({"password": list(exc.messages)}) from exc

        try:
            user.set_password(new_password)
            user.save()
        except Exception:
            logger.exception("password_reset_confirm: failed to save user. user_id=%s", user.id)
            return Response(
                {"detail": "Unable to reset password. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            redis_blacklist.clear_user_tokens(user.id)
        except Exception:
            logger.warning(
                "password_reset_confirm: token blacklist clear failed. user_id=%s",
                user.id,
                exc_info=True,
            )

        secure_reset.log_reset_attempt(user.email, ip_address, "PASSWORD_RESET_SUCCESS", True)
        return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

@extend_schema(
    tags=["Password Management"],
    summary="Validate Reset Token",
    description="Validate password reset token before submitting a new password.",
    request=PasswordResetValidateSerializer,
)
class PasswordResetValidateView(GenericAPIView):
    serializer_class = PasswordResetValidateSerializer
    """Let the frontend check uid/token before collecting a new password."""

    permission_classes = [permissions.AllowAny]
    throttle_scope = "password_reset_validate"

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]

        validation = validate_reset_token(uid, token)
        return Response({"valid": bool(validation.is_valid and validation.user)})

@extend_schema(
    tags=["Password Management"],
    summary="Request OTP Reset",
    description="Send OTP for password reset.",
    request=PasswordResetOTPSerializer,
)
class PasswordResetOTPView(GenericAPIView):
    serializer_class = PasswordResetOTPSerializer
    """OTP-based password reset (mobile-friendly)."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        rate_limit_ok, rate_limit_msg = otp_reset.check_rate_limit(email)
        if not rate_limit_ok:
            return Response({"detail": rate_limit_msg}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        if not User.objects.filter(email=email).exists():
            return Response(status=status.HTTP_204_NO_CONTENT)

        otp = otp_reset.generate_otp()
        if not otp_reset.store_otp(email, otp):
            return Response(
                {"detail": "Unable to process reset request"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not otp_reset.send_otp_email(email, otp):
            return Response({"detail": "Unable to send OTP"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        otp_reset.increment_rate_limit(email)

        return Response(status=status.HTTP_204_NO_CONTENT)

@extend_schema(
    tags=["Password Management"],
    summary="Confirm OTP Reset",
    description="Reset password using OTP.",
    request=PasswordResetConfirmOTPSerializer,
)
class PasswordResetConfirmOTPView(GenericAPIView):
    serializer_class = PasswordResetConfirmOTPSerializer
    """Confirm password reset with OTP."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        otp_valid, otp_msg = otp_reset.verify_otp(email, otp)
        if not otp_valid:
            return Response({"detail": otp_msg}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "Invalid reset request"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response(status=status.HTTP_204_NO_CONTENT)
