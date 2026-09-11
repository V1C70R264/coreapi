from rest_framework import serializers
from .models import Cart, CartItem

class CartItemSerializer(serializers.ModelSerializer):

    total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            'id',
            'cart',
            'product',
            'quantity',
            'total_price',
            'added_at',
        ]
        read_only_fields = [
            'cart',
            'total_price',
            'added_at',
        ]

    def get_total_price(self, obj):
        return obj.get_total_price()

    def validate_product(self, value):
        if value.stock_quantity < 1:
            raise serializers.ValidationError("Product is out of stock.")
        return value

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Quantity must be at least 1."
            )
        return value

    def validate(self, data):
        product = data.get('product')

        if product is None and self.instance is not None:
            product = self.instance.product

        if self.instance is not None:
            if 'product' in data and data['product'] != self.instance.product:
                raise serializers.ValidationError(
                    {
                        "product": "The product cannot be changed once it has been added to the cart."
                    }
                )

        quantity = data.get('quantity')

        if quantity is None:
            return data
        
        if self.instance is None:
        
            request = self.context.get('request')

            if not request or not request.user.is_authenticated:
                return data

            cart = Cart.objects.filter(user=request.user).first()

            if cart:
                existing_item = CartItem.objects.filter(
                    cart=cart,
                    product=product
                ).first()

                existing_quantity = existing_item.quantity if existing_item else 0

                if existing_quantity + quantity > product.stock_quantity:
                    raise serializers.ValidationError(
                        {
                            "quantity": (
                                f"Only {product.stock_quantity - existing_quantity} "
                                f"unit(s) of this product are available to add."
                            )
                        }
                    )

        else:
            if quantity > product.stock_quantity:
                raise serializers.ValidationError(
                    {
                         "quantity": (
                            f"Only {product.stock_quantity} "
                            f"unit(s) of this product are available."
                )
                    }
                )

        return data

    # def get_fields(self):
    #     fields = super().get_fields()

    #     if self.instance is not None:
    #         fields['product'].read_only = True

    #     return fields


class CartSerializer(serializers.ModelSerializer):

    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            'id',
            'user',
            'items',
            'total_price',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'user',
            'items',
            'total_price',
            'created_at',
            'updated_at',
        ]

    def get_total_price(self, obj):
        return sum(
            item.get_total_price()
            for item in obj.items.all()
        )