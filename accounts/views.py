from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetOTPSerializer,
    PasswordResetConfirmOTPSerializer,
    ChangePasswordSerializer,
    GoogleAuthSerializer,
    UserProfileSerializer,
)
from .redis_blacklist import redis_blacklist
from .secure_reset import secure_reset
from .otp_reset import otp_reset

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({'id': user.id, 'email': user.email, 'username': user.username}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.save()
        return Response(tokens, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        # Get client IP for rate limiting and audit
        ip_address = request.META.get('REMOTE_ADDR', 'unknown')
        
        # Check rate limits
        rate_limit_ok, rate_limit_msg = secure_reset.check_rate_limit(email, ip_address)
        if not rate_limit_ok:
            secure_reset.log_reset_attempt(email, ip_address, 'RATE_LIMIT_EXCEEDED', False)
            return Response({'detail': rate_limit_msg}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Check if user exists (don't reveal if they don't for security)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Log attempt but don't reveal user doesn't exist
            secure_reset.log_reset_attempt(email, ip_address, 'RESET_REQUEST', False)
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        # Generate secure token
        token = secure_reset.generate_secure_token()
        
        # Store token in Redis
        if not secure_reset.store_reset_token(email, token):
            secure_reset.log_reset_attempt(email, ip_address, 'TOKEN_STORAGE_FAILED', False)
            return Response({'detail': 'Unable to process reset request'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Increment rate limit
        secure_reset.increment_rate_limit(email)
        
        # Create secure reset link
        reset_link = f"{request.scheme}://{request.get_host()}/api/auth/password-reset/confirm/?token={token}&email={email}"
        
        # Send email
        send_mail(
            subject='Password Reset Request',
            message=f'Click the link to reset your password (valid for 15 minutes): {reset_link}',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[email],
            fail_silently=True,
        )
        
        # Log successful request
        secure_reset.log_reset_attempt(email, ip_address, 'RESET_REQUEST', True)
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        # Get client IP for audit
        ip_address = request.META.get('REMOTE_ADDR', 'unknown')
        
        # Verify and consume token (single-use)
        token_valid, token_msg = secure_reset.verify_and_consume_token(email, token)
        if not token_valid:
            secure_reset.log_reset_attempt(email, ip_address, 'INVALID_TOKEN', False)
            return Response({'detail': token_msg}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            secure_reset.log_reset_attempt(email, ip_address, 'USER_NOT_FOUND', False)
            return Response({'detail': 'Invalid reset request'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update password
        user.set_password(new_password)
        user.save()
        
        # Log successful reset
        secure_reset.log_reset_attempt(email, ip_address, 'PASSWORD_RESET_SUCCESS', True)
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            
            # Use Redis blacklist instead of database
            print(f"DEBUG: Attempting to blacklist token with JTI: {token.payload.get('jti')}")
            blacklist_result = redis_blacklist.blacklist_token(token)
            print(f"DEBUG: Blacklist result: {blacklist_result}")
            
            if blacklist_result:
                print("DEBUG: Token successfully blacklisted")
                return Response(status=status.HTTP_205_RESET_CONTENT)
            else:
                print("DEBUG: Failed to blacklist token")
                return Response({'detail': 'Failed to blacklist token'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except TokenError:
            return Response({'detail': 'Token is blacklisted'}, status=status.HTTP_400_BAD_REQUEST)
        except KeyError:
            return Response({'detail': 'Refresh token required'}, status=status.HTTP_400_BAD_REQUEST)


class GoogleAuthView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'google_auth'

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data['google']
        email = data.get('email')
        first_name = data.get('given_name') or ''
        last_name = data.get('family_name') or ''

        # Create or get user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': first_name,
                'last_name': last_name,
            },
        )

        # Issue JWTs
        refresh = RefreshToken.for_user(user)
        return Response({'access': str(refresh.access_token), 'refresh': str(refresh)}, status=status.HTTP_200_OK)


class TokenRefresh(TokenRefreshView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        """
        Override to check if refresh token is blacklisted before issuing new tokens
        """
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({'detail': 'Refresh token required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Parse the refresh token to check if it's blacklisted
            token = RefreshToken(refresh_token)
            print(f"DEBUG: TokenRefresh - Checking refresh token JTI: {token.payload.get('jti')}")
            
            # Check if the refresh token is blacklisted
            if redis_blacklist.is_token_blacklisted(token):
                print("DEBUG: TokenRefresh - Refresh token is blacklisted, rejecting")
                return Response({'detail': 'Token is blacklisted'}, status=status.HTTP_401_UNAUTHORIZED)
            
            # If not blacklisted, proceed with normal token refresh
            print("DEBUG: TokenRefresh - Refresh token is valid, issuing new tokens")
            return super().post(request, *args, **kwargs)
            
        except TokenError as e:
            print(f"DEBUG: TokenRefresh - Token error: {e}")
            return Response({'detail': 'Token is invalid or expired'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            print(f"DEBUG: TokenRefresh - Unexpected error: {e}")
            return Response({'detail': 'Token refresh failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==========================================
# MODERN PASSWORD RESET FLOW (OTP-Based)
# ==========================================

class PasswordResetOTPView(APIView):
    """Modern OTP-based password reset (Mobile-friendly)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        
        # Check rate limits
        rate_limit_ok, rate_limit_msg = otp_reset.check_rate_limit(email)
        if not rate_limit_ok:
            return Response({'detail': rate_limit_msg}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Check if user exists (don't reveal for security)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        # Generate and store OTP
        otp = otp_reset.generate_otp()
        if not otp_reset.store_otp(email, otp):
            return Response({'detail': 'Unable to process reset request'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Send OTP via email
        if not otp_reset.send_otp_email(email, otp):
            return Response({'detail': 'Unable to send OTP'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Increment rate limit
        otp_reset.increment_rate_limit(email)
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetConfirmOTPView(APIView):
    """Confirm password reset with OTP"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']
        
        # Verify OTP
        otp_valid, otp_msg = otp_reset.verify_otp(email, otp)
        if not otp_valid:
            return Response({'detail': otp_msg}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get user and update password
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'detail': 'Invalid reset request'}, status=status.HTTP_400_BAD_REQUEST)
        
        user.set_password(new_password)
        user.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==========================================
# CHANGE PASSWORD (User Logged In)
# ==========================================

class ChangePasswordView(APIView):
    """Change password when user is logged in"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']
        
        # Verify current password
        if not request.user.check_password(current_password):
            return Response({'detail': 'Current password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Update password
        request.user.set_password(new_password)
        request.user.save()
        
        # Optional: Logout user from other sessions for security
        # This would require additional implementation
        
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)