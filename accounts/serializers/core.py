from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from ..models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'first_name', 'last_name', 'phone',)

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

        user = User.objects.authenticate_by_email(email, password)
        if not user:
            raise serializers.ValidationError(_('Invalid credentials'))

        attrs['user'] = user
        return attrs

    def create(self, validated_data):
        from ..services.token_service import TokenService

        user = validated_data['user']
        return TokenService().issue_tokens_for_user(user)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Confirm reset with uid, Django ``PasswordResetTokenGenerator`` token, and new password."""

    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=1)


class PasswordResetValidateSerializer(serializers.Serializer):
    """Optional: validate uid/token before showing the new-password form."""

    uid = serializers.CharField()
    token = serializers.CharField()


class PasswordResetOTPSerializer(serializers.Serializer):
    """Serializer for requesting OTP."""

    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            pass
        return value


class PasswordResetConfirmOTPSerializer(serializers.Serializer):
    """Serializer for confirming password reset with OTP."""

    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        validate_password(value)
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password when logged in."""

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


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True)
    avatar = serializers.ImageField(required=False, allow_null=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'full_name',
            'initials',
            'phone',
            'avatar',
            'avatar_url',
            'auth_provider',
            'email_verified',
            'last_login_provider',
        )
        read_only_fields = (
            'id',
            'email',
            'full_name',
            'initials',
            'avatar_url',
            'auth_provider',
            'email_verified',
            'last_login_provider',
        )

    def get_avatar_url(self, obj):
        if obj.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def validate_username(self, value):
        if self.instance:
            try:
                self.instance.validate_username(value)
            except ValidationError as exc:
                raise serializers.ValidationError(str(exc))
        return value

    def validate_first_name(self, value):
        if value and self.instance:
            try:
                return self.instance.validate_first_name(value)
            except ValidationError as exc:
                raise serializers.ValidationError(str(exc))
        return value

    def validate_last_name(self, value):
        if value and self.instance:
            try:
                return self.instance.validate_last_name(value)
            except ValidationError as exc:
                raise serializers.ValidationError(str(exc))
        return value

    def validate_phone(self, value):
        if value and self.instance:
            try:
                return self.instance.validate_phone(value)
            except ValidationError as exc:
                raise serializers.ValidationError(str(exc))
        return value

    def update(self, instance, validated_data):
        avatar = validated_data.pop('avatar', None)
        clear_avatar = avatar is None and 'avatar' in validated_data

        instance.update_profile(
            username=validated_data.get('username'),
            first_name=validated_data.get('first_name'),
            last_name=validated_data.get('last_name'),
            phone=validated_data.get('phone'),
            avatar=avatar,
            clear_avatar=clear_avatar,
        )
        return instance
