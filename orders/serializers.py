from rest_framework import serializers
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .models import Order, OrderItem
from products.models import Product
from addresses.models import Address


class OrderItemSerializer(serializers.ModelSerializer):
    # ... unchanged from before ...
    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value

    class Meta:
        model = OrderItem
        fields = [
            'id', 'order', 'product', 'product_image_url',
            'product_name', 'quantity', 'unit_price', 'subtotal',
        ]
        read_only_fields = [
            'id', 'order', 'product_image_url',
            'product_name', 'unit_price', 'subtotal',
        ]


class OrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(many=True)

    # Write-only on input: the client sends the ID of one of their
    # own saved addresses. Never exposed as writable on read/update —
    # the actual shipping fields below are what gets returned.
    shipping_address_id = serializers.PrimaryKeyRelatedField(
        queryset=Address.objects.none(),  # overridden per-request in __init__
        write_only=True,
        source='shipping_address',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request is not None:
            # Scope the allowed addresses to the requester's own —
            # prevents a user from passing another user's address id.
            self.fields['shipping_address_id'].queryset = Address.objects.filter(
                user=request.user
            )

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Order must contain at least one item.")

        product_ids = [item['product'].id for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("A product can only appear once in an order.")

        for item in value:
            if item['quantity'] > item['product'].stock_quantity:
                raise serializers.ValidationError(
                    f"Only {item['product'].stock_quantity} unit(s) of "
                    f"'{item['product'].name}' left in stock."
                )
        return value

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        address = validated_data.pop('shipping_address')
        request = self.context.get('request')

        product_ids = [item['product'].id for item in items_data]
        locked_products = {
            p.id: p
            for p in Product.objects.select_for_update()
                .filter(id__in=product_ids).order_by('id')
        }

        items_to_create = []
        total_amount = Decimal('0.00')

        for item_data in items_data:
            product = locked_products[item_data['product'].id]
            quantity = item_data['quantity']

            if quantity > product.stock_quantity:
                raise serializers.ValidationError({
                    'items': f"Only {product.stock_quantity} unit(s) of "
                             f"'{product.name}' left in stock."
                })

            unit_price = product.price
            subtotal = unit_price * quantity
            total_amount += subtotal

            if product.image:
                image_url = product.image.url
                if request is not None:
                    image_url = request.build_absolute_uri(image_url)
            else:
                image_url = ''

            items_to_create.append({
                'product': product,
                'product_image_url': image_url,
                'product_name': product.name,
                'quantity': quantity,
                'unit_price': unit_price,
                'subtotal': subtotal,
            })

        scheduled_delivery_date = timezone.now().date() + timedelta(days=2)

        order = Order.objects.create(
            **validated_data,
            customer=request.user,
            total_amount=total_amount,
            scheduled_delivery_date=scheduled_delivery_date,
            shipping_address=address,
            recipient_name=address.full_name,
            recipient_phone=address.phone_number,
            shipping_region=address.region,
            shipping_district=address.district,
            shipping_street_address=address.street_address,
        )

        OrderItem.objects.bulk_create([
            OrderItem(order=order, **item_data)
            for item_data in items_to_create
        ])

        for item_data in items_to_create:
            updated = Product.objects.filter(
                id=item_data['product'].id,
                stock_quantity__gte=item_data['quantity'],
            ).update(stock_quantity=F('stock_quantity') - item_data['quantity'])

            if not updated:
                raise serializers.ValidationError({
                    'items': f"'{item_data['product'].name}' went out of stock."
                })

        return order

    def update(self, instance, validated_data):
        validated_data.pop('items', None)
        return super().update(instance, validated_data)

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'order_number', 'status', 'total_amount',
            'created_at', 'updated_at', 'scheduled_delivery_date',
            'shipping_address_id',
            'recipient_name', 'recipient_phone',
            'shipping_region', 'shipping_district', 'shipping_street_address',
            'items',
        ]
        read_only_fields = [
            'id', 'customer', 'order_number', 'status', 'total_amount',
            'created_at', 'updated_at', 'scheduled_delivery_date',
            'recipient_name', 'recipient_phone',
            'shipping_region', 'shipping_district', 'shipping_street_address',
        ]