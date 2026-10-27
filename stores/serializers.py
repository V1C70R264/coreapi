from rest_framework import serializers
from .models import Store


class StoreSerializer(serializers.ModelSerializer):
    """Public view of an approved store."""
    logo_url = serializers.SerializerMethodField()
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'description', 'logo_url',
            'product_count', 'created_at',
        ]

    def get_logo_url(self, obj):
        return obj.logo.url if obj.logo else None


class MyStoreSerializer(serializers.ModelSerializer):
    """What the owner sees about their own store, in any status."""
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = [
            'id', 'name', 'description', 'logo_url',
            'status', 'rejection_reason', 'created_at',
        ]

    def get_logo_url(self, obj):
        return obj.logo.url if obj.logo else None


class StoreApplicationSerializer(serializers.ModelSerializer):
    """Input for applying (or re-applying after a rejection)."""

    class Meta:
        model = Store
        fields = ['name', 'description']

    def validate_name(self, value):
        # CharField already trims whitespace, and the model's unique=True
        # adds a uniqueness check automatically.
        if len(value) < 3:
            raise serializers.ValidationError(
                "Store name must be at least 3 characters."
            )
        return value