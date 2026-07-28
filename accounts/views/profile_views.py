from drf_spectacular.utils import extend_schema
from django.core.exceptions import ValidationError
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView

from ..email_service import send_plain_email
from ..redis_blacklist import redis_blacklist
from ..serializers import (
    AvatarRemoveSerializer,
    AvatarUploadSerializer,
    ChangePasswordSerializer,
    UserProfileSerializer,
    EmailTestSerializer,
)


@extend_schema(
    tags=["Profile"],
    summary="Change Password",
    description="Allow authenticated user to change password.",
    request=ChangePasswordSerializer,
)
class ChangePasswordView(GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        current_password = serializer.validated_data["current_password"]
        new_password = serializer.validated_data["new_password"]

        try:
            request.user.change_password(current_password, new_password)
        except ValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        redis_blacklist.clear_user_tokens(request.user.id)

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Profile"],
    summary="User Profile",
    description=(
        "Retrieve and update the authenticated user's profile. "
        "To upload or change the avatar, send `multipart/form-data` with the `avatar` field. "
        "To clear the avatar without replacing it, include `remove_avatar=true`. "
        "For avatar-only operations, prefer the dedicated `/users/me/avatar/` endpoint."
    ),
    request={"multipart/form-data": UserProfileSerializer, "application/json": UserProfileSerializer},
    responses=UserProfileSerializer,
)
class ProfileView(GenericAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        serializer = self.get_serializer(
            request.user,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = self.get_serializer(
            request.user,
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = self.get_serializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Profile"],
    summary="Avatar Management",
    description=(
        "Dedicated endpoint for profile picture operations.\n\n"
        "**PUT** — Upload or replace the current avatar. "
        "Send `multipart/form-data` with a single `avatar` field containing the image file. "
        "Supported formats: JPEG, PNG, WebP, GIF.\n\n"
        "**DELETE** — Remove the current avatar. No request body needed."
    ),
)
class AvatarView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary="Upload / Replace Avatar",
        request={"multipart/form-data": AvatarUploadSerializer},
        responses={200: UserProfileSerializer},
    )
    def put(self, request):
        """Upload a new avatar (replaces existing one on Cloudinary)."""
        serializer = AvatarUploadSerializer(
            instance=request.user,
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        response_serializer = UserProfileSerializer(user, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Remove Avatar",
        request=None,
        responses={200: AvatarRemoveSerializer},
    )
    def delete(self, request):
        """Remove the current avatar from Cloudinary and the database."""
        user = request.user
        if user.avatar:
            try:
                import cloudinary.uploader
                old_public_id = user.avatar.name
                if old_public_id:
                    cloudinary.uploader.destroy(old_public_id)
            except Exception:
                pass  # Best-effort cleanup
            user.avatar = None
            user.save(update_fields=["avatar"])

        return Response(
            {"detail": "Avatar removed successfully.", "avatar_url": None},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Administration"],
    summary="SMTP Email Test",
    description="Admin-only endpoint for testing email delivery.",
    request=EmailTestSerializer,
)
class EmailTestView(GenericAPIView):
    serializer_class = EmailTestSerializer
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        to = serializer.validated_data.get("to") or "victorshirima295@gmail.com"

        result = send_plain_email(
            subject="CoreAPI SMTP test (admin endpoint)",
            body="If you received this, the admin email test endpoint succeeded.\n",
            recipient_list=[to],
        )

        if result.ok:
            return Response(
                {"detail": "sent", "to": to},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"detail": result.message, "code": result.error_code},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )