import logging
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.utils import extend_schema
from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.generics import GenericAPIView

from ..redis_blacklist import redis_blacklist
from ..serializers import (
    GoogleIdTokenSerializer,
    LoginSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    LogoutSerializer,
    EmailTestSerializer
)
from ..services.google_auth_service import GoogleAuthService
from ..utils.oauth_errors import OAuthAccountConflictError, OAuthTokenError

logger = logging.getLogger(__name__)

User = get_user_model()

@extend_schema(
    tags=["Authentication"],
    summary="Register User",
    description="Create a new user account.",
    request=RegisterSerializer,
)
class RegisterView(GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        return Response(
            {
                "id": user.id,
                "email": user.email,
                "username": user.username,
            },
            status=status.HTTP_201_CREATED,
        )

@extend_schema(
    tags=["Authentication"],
    summary="Login User",
    description="Authenticate user and return JWT access and refresh tokens.",
    request=LoginSerializer,
)
class LoginView(GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tokens = serializer.save()

        return Response(tokens, status=status.HTTP_200_OK)

@extend_schema(
    tags=["Authentication"],
    summary="Logout User",
    description="Blacklist refresh token and logout user.",
    request=LogoutSerializer,
)
class LogoutView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            refresh_token = serializer.validated_data["refresh"]

            token = RefreshToken(refresh_token)

            blacklist_result = redis_blacklist.blacklist_token(token)

            if not blacklist_result:
                logger.warning(
                    "Could not blacklist refresh token (Redis unavailable). Returning 205 anyway."
                )

            return Response(status=status.HTTP_205_RESET_CONTENT)

        except TokenError:
            return Response(
                {"detail": "Token is blacklisted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

@extend_schema(
    tags=["Authentication"],
    summary="Google Authentication",
    description="Authenticate user using Google OAuth ID token.",
    request=GoogleIdTokenSerializer,
)
class GoogleAuthView(GenericAPIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = "google_auth"

    serializer_class = GoogleIdTokenSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            tokens, user = GoogleAuthService.default().sign_in_with_google(
                id_token=serializer.validated_data["id_token"]
            )

        except OAuthTokenError as exc:
            return Response(
                {"detail": exc.message},
                status=exc.status_code,
            )

        except OAuthAccountConflictError:
            return Response(
                {"detail": "Unable to sign in with this Google account."},
                status=status.HTTP_409_CONFLICT,
            )

        user_data = UserProfileSerializer(
            user,
            context={"request": request},
        ).data

        return Response(
            {
                **tokens,
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )

@extend_schema(
    tags=["Authentication"],
    summary="Refresh JWT Token",
    description="Generate a new access token using a refresh token.",
)
class TokenRefresh(TokenRefreshView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        """Reject blacklisted refresh tokens before SimpleJWT rotates."""
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({'detail': 'Refresh token required'}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            logger.debug('TokenRefresh: checking refresh token jti=%s', token.payload.get('jti'))

            if redis_blacklist.is_token_blacklisted(token):
                logger.info('TokenRefresh: rejected blacklisted refresh token.')
                return Response({'detail': 'Token is blacklisted'}, status=status.HTTP_401_UNAUTHORIZED)

            return super().post(request, *args, **kwargs)

        except TokenError as exc:
            logger.info('TokenRefresh: invalid token: %s', exc)
            return Response({'detail': 'Token is invalid or expired'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as exc:
            logger.exception('TokenRefresh: unexpected error: %s', exc)
            return Response({'detail': 'Token refresh failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
