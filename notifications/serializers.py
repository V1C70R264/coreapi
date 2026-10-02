from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'body',
            'order', 'is_read', 'created_at',
        ]
        read_only_fields = fields  # every field — these are only ever
        # created by signals, never by a client POST