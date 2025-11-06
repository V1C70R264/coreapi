from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
import requests

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'first_name', 'last_name')

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            username = None
        user = authenticate(username=username, password=password) if username else None
        if not user:
            raise serializers.ValidationError(_('Invalid credentials'))
        if not user.is_active:
            raise serializers.ValidationError(_('User account is disabled'))
        attrs['user'] = user
        return attrs

    def create(self, validated_data):
        user = validated_data['user']
        refresh = RefreshToken.for_user(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
    def validate_email(self, value):
        # Check if email exists
        from .models import User
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            pass
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Legacy email-link reset confirm (email + token)."""
    email = serializers.EmailField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class PasswordResetOTPSerializer(serializers.Serializer):
    """Serializer for requesting OTP"""
    email = serializers.EmailField()
    
    def validate_email(self, value):
        from .models import User
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            # Don't reveal if email exists for security
            pass
        return value


class PasswordResetConfirmOTPSerializer(serializers.Serializer):
    """Serializer for confirming password reset with OTP"""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password when logged in"""
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs

    def validate_new_password(self, value):
        validate_password(value)
        return value


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(write_only=True)

    def validate(self, attrs):
        id_token = attrs.get('id_token')
        # Verify token against Google tokeninfo endpoint
        try:
            resp = requests.get('https://oauth2.googleapis.com/tokeninfo', params={'id_token': id_token}, timeout=5)
        except requests.RequestException:
            raise serializers.ValidationError(_('Verification service unavailable, try again'))
        if resp.status_code != 200:
            raise serializers.ValidationError(_('Invalid Google token'))
        data = resp.json()

        # Validate audience/client id
        aud = data.get('aud') or data.get('audience')
        allowed = getattr(settings, 'GOOGLE_CLIENT_IDS', [])
        if allowed and aud not in allowed:
            raise serializers.ValidationError(_('Unauthorized Google client'))

        # Issuer and basic checks
        iss = data.get('iss')
        if iss not in {'https://accounts.google.com', 'accounts.google.com'}:
            raise serializers.ValidationError(_('Invalid token issuer'))
        email = data.get('email')
        email_verified = data.get('email_verified') in (True, 'true', 'True', '1', 1)
        if not email or not email_verified:
            raise serializers.ValidationError(_('Google email not verified'))

        attrs['google'] = data
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True)
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name', 'avatar',
        )

    def validate_username(self, value):
        if not value:
            return value
        user = self.instance
        if user and user.username == value:
            return value
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('This username is already taken')
        return value

    def update(self, instance, validated_data):
        for field in ['username', 'first_name', 'last_name']:
            if field in validated_data:
                setattr(instance, field, validated_data[field])

        # Handle avatar separately to allow clearing with null
        if 'avatar' in validated_data:
            avatar = validated_data.get('avatar')
            instance.avatar = avatar

        instance.save()
        return instance