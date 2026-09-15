from rest_framework import serializers
from .models import Address


class AddressSerializer(serializers.ModelSerializer):

    def validate(self, attrs):
        request = self.context.get('request')
        if request and self.instance is None:  # only cap on create, not update
            existing_count = Address.objects.filter(user=request.user).count()
            if existing_count >= 10:
                raise serializers.ValidationError(
                    "You can have at most 10 saved addresses."
                )
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['user'] = request.user
        return super().create(validated_data)

    class Meta:
        model = Address
        fields = [
            'id', 'user', 'label', 'full_name', 'phone_number',
            'region', 'district', 'street_address', 'is_default',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'user', 'created_at', 'updated_at',
        ]