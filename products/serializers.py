from rest_framework import serializers
from .models import Product, Category
from favorites.models import Favorite
from stores.models import StoreStatus


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
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    store_id = serializers.SerializerMethodField()
    store_name = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock_quantity',
            'category', 'category_details', 'seller', 'image',
            'is_favorited', 'created_at', 'updated_at', 'average_rating', 'review_count', 'store_id', 'store_name',
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
    def get_average_rating(self, obj):
        # obj.reviews is the related_name from Review.product
        reviews = obj.reviews.all()
        if not reviews:
            return None
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    def get_review_count(self, obj):
        return obj.reviews.count()

    def _public_store(self, obj):
        # Only an approved, active store is shown publicly. The reverse
        # one-to-one raises an AttributeError subclass when the seller has
        # no store, so getattr with a default returns None in that case.
        seller = obj.seller
        if seller is None:
            return None
        store = getattr(seller, 'store', None)
        if store and store.status == StoreStatus.APPROVED and store.is_active:
            return store
        return None

    def get_store_id(self, obj):
        store = self._public_store(obj)
        return store.id if store else None

    def get_store_name(self, obj):
        store = self._public_store(obj)
        return store.name if store else None
class ProductMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'price', 'image']