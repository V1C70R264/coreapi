from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Notification
from .serializers import NotificationSerializer


@extend_schema(tags=["Notifications"])
@extend_schema_view(
    list=extend_schema(
        summary="List my notifications",
        description="Returns the authenticated user's notifications, newest first.",
    ),
    retrieve=extend_schema(
        summary="Retrieve a notification",
        description="Returns a single notification belonging to the authenticated user.",
    ),
)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # the app wants the full set to compute counts/badges

    def get_queryset(self):
        return Notification.objects.filter(
            user=self.request.user
        ).select_related('order')

    @extend_schema(
        summary="Unread notification count",
        description="Returns how many of the authenticated user's notifications are unread.",
    )
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})

    @extend_schema(
        summary="Mark a notification as read",
        description="Marks a single notification as read.",
    )
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        summary="Mark all notifications as read",
        description="Marks every one of the authenticated user's notifications as read.",
    )
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({'marked_read': updated}, status=status.HTTP_200_OK)