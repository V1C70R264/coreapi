from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from drf_spectacular.openapi import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
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


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailTestSerializer(serializers.Serializer):
    to = serializers.EmailField(required=False)


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
    avatar = extend_schema_field(OpenApiTypes.BINARY)(
        serializers.ImageField(required=False, allow_null=True, write_only=True)
    )
    remove_avatar = serializers.BooleanField(write_only=True, required=False, default=False)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'full_name', 'initials', 'phone',
            'avatar', 'remove_avatar', 'avatar_url',
            'auth_provider', 'email_verified', 'last_login_provider',
        )
        read_only_fields = (
            'id', 'email', 'full_name', 'initials', 'avatar_url',
            'auth_provider', 'email_verified', 'last_login_provider',
        )

    def get_avatar_url(self, obj):
        # Cloudinary storage already returns an absolute URL — do NOT wrap with
        # build_absolute_uri, which would corrupt it by prepending the request host.
        if obj.avatar:
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
        remove_avatar = validated_data.pop('remove_avatar', False)
        avatar = validated_data.pop('avatar', serializers.empty)

        avatar_provided = avatar is not serializers.empty
        clear_avatar = remove_avatar and not avatar_provided
        if not avatar_provided:
            avatar = None  # sentinel resolved -> "don't touch it" unless clear_avatar is True

        instance.update_profile(
            username=validated_data.get('username', instance.username),
            first_name=validated_data.get('first_name', instance.first_name),
            last_name=validated_data.get('last_name', instance.last_name),
            phone=validated_data.get('phone', instance.phone),
            avatar=avatar,
            clear_avatar=clear_avatar,
        )
        return instance


class AvatarUploadSerializer(serializers.Serializer):
    """Dedicated serializer for avatar upload (PUT / PATCH on /users/me/avatar/)."""

    avatar = extend_schema_field(OpenApiTypes.BINARY)(
        serializers.ImageField(
            required=True,
            help_text="Profile picture file (JPEG, PNG, WebP, etc.)",
        )
    )

    def update(self, instance, validated_data):
        import cloudinary.uploader
        new_avatar = validated_data['avatar']
        # Delete previous Cloudinary asset before uploading the new one
        if instance.avatar:
            try:
                # Extract public_id from the existing Cloudinary URL / name
                old_public_id = instance.avatar.name
                if old_public_id:
                    cloudinary.uploader.destroy(old_public_id)
            except Exception:
                pass  # Best-effort cleanup – don't break the upload
        instance.avatar = new_avatar
        instance.save(update_fields=['avatar'])
        return instance


class AvatarRemoveSerializer(serializers.Serializer):
    """Response serializer when avatar is removed."""

    detail = serializers.CharField(read_only=True, default="Avatar removed successfully.")
    avatar_url = serializers.CharField(read_only=True, allow_null=True, default=None)