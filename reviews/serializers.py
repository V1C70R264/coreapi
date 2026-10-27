from rest_framework import serializers
from orders.models import OrderItem, OrderStatus
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'id', 'user', 'user_name', 'product',
            'rating', 'comment', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_user_name(self, obj):
        # Shows a display name without exposing the reviewer's email —
        # falls back to username if no name is set.
        full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full_name or obj.user.username

    def validate_product(self, value):
        request = self.context.get('request')
        user = request.user

        has_delivered_purchase = OrderItem.objects.filter(
            order__customer=user,
            order__status=OrderStatus.DELIVERED,
            product=value,
        ).exists()

        if not has_delivered_purchase:
            raise serializers.ValidationError(
                "You can only review products from orders that have been delivered to you."
            )

        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user'] = request.user
        return super().create(validated_data)