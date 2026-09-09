from rest_framework import serializers
from .models import Product, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'description']

class ProductSerializer(serializers.ModelSerializer):
    seller = serializers.PrimaryKeyRelatedField(
            read_only=True,
        )
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        write_only=True
    )

    category_details = CategorySerializer(
        source='category',
        read_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock_quantity', 
            'category', 'category_details', 'seller', 'image', 'created_at', 'updated_at'
        ]
    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

    # the product name and description must not be the same
    def validate(self, data):
        name = data.get('name', getattr(self.instance, 'name', None))
        description = data.get(
           'description',
            getattr(self.instance, 'description', None)
      )
        if name == description:
            raise serializers.ValidationError(
            "Product name and description must not be the same."
        )
        return data

    # def validate_stock_quantity(self, value):
    #     if value <= 0:
    #         raise serializers.ValidationError("Stock quantity must be a positive integer.")
    #     return value

    # def validate_name(self, value):
    #     if not value:
    #         raise serializers.ValidationError("Name is required.")
    #     return value

    # def validate_description(self, value):
    #     if not value:
    #         raise serializers.ValidationError("Description is required.")
    #     return value

