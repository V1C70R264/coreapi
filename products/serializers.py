from rest_framework import serializers
from .models import Product, Category
from favorites.models import Favorite


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

    is_favorited = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock_quantity',
            'category', 'category_details', 'seller', 'image',
            'is_favorited', 'created_at', 'updated_at'
        ]

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request is None or not request.user.is_authenticated:
            return False
        return Favorite.objects.filter(user=request.user, product=obj).exists()

    def validate_image(self, value):
        if not value:
            raise serializers.ValidationError("An image is required to create a product.")
        return value

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value

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

class ProductMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'image']