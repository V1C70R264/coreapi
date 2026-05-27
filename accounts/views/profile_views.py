from django.core.exceptions import ValidationError
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from ..email_service import send_plain_email
from ..redis_blacklist import redis_blacklist
from ..serializers import ChangePasswordSerializer, UserProfileSerializer


class ChangePasswordView(APIView):
    """Change password when user is logged in."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        try:
            request.user.change_password(current_password, new_password)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        redis_blacklist.clear_user_tokens(request.user.id)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class EmailTestView(APIView):
    """
    Staff-only SMTP smoke test. Exposed only when ENABLE_EMAIL_TEST_API=true.
    POST JSON: {"to": "optional@example.com"} (defaults to victorshirima295@gmail.com).
    """

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        to = (request.data.get('to') or '').strip() or 'victorshirima295@gmail.com'
        result = send_plain_email(
            subject='CoreAPI SMTP test (admin endpoint)',
            body='If you received this, the admin email test endpoint succeeded.\n',
            recipient_list=[to],
        )
        if result.ok:
            return Response({'detail': 'sent', 'to': to}, status=status.HTTP_200_OK)
        return Response(
            {'detail': result.message, 'code': result.error_code},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
