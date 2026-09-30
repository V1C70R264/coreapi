from rest_framework import serializers
from products.serializers import ProductSerializer
from .models import Favorite


class FavoriteSerializer(serializers.ModelSerializer):
    product_detail = ProductSerializer(source='product', read_only=True)

    class Meta:
        model = Favorite
        fields = ['id', 'product', 'product_detail', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_product(self, value):
        request = self.context.get('request')
        if Favorite.objects.filter(user=request.user, product=value).exists():
            raise serializers.ValidationError("This product is already in your favorites.")
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user'] = request.user
        return super().create(validated_data)