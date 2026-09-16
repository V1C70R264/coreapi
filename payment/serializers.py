from rest_framework import serializers
from .models import Payment
from orders.models import Order, OrderStatus


class PaymentInitiateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()

    def validate_order_id(self, value):
        request = self.context.get('request')
        try:
            order = Order.objects.get(id=value, customer=request.user)
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found.")

        if order.status != OrderStatus.PENDING:
            raise serializers.ValidationError(
                f"Cannot pay for an order in '{order.status}' status."
            )

        # Don't allow initiating a new payment if one is already
        # successful for this order (shouldn't happen given the
        # status check above, but guards against a stale PENDING order
        # that already has a successful payment row for some reason).
        if order.payments.filter(status='successful').exists():
            raise serializers.ValidationError("This order has already been paid for.")

        self.order = order
        return value


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'tx_ref', 'gateway_transaction_id', 'gateway',
            'amount', 'currency', 'status', 'payment_method',
            'paid_at', 'created_at', 'updated_at',
        ]
        read_only_fields = fields  # payments are never client-editable