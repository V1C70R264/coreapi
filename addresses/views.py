from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Address
from .serializers import AddressSerializer


@extend_schema(tags=["Addresses"])
@extend_schema_view(
    list=extend_schema(
        summary="List addresses",
        description="Returns all saved addresses belonging to the authenticated user.",
    ),
    retrieve=extend_schema(
        summary="Retrieve an address",
        description="Returns a single address, if it belongs to the authenticated user.",
    ),
    create=extend_schema(
        summary="Create an address",
        description=(
            "Creates a new address for the authenticated user. "
            "The first address a user creates automatically becomes their default."
        ),
    ),
    update=extend_schema(
        summary="Update an address",
        description="Fully replaces an existing address belonging to the authenticated user.",
    ),
    partial_update=extend_schema(
        summary="Partially update an address",
        description="Updates one or more fields of an existing address belonging to the authenticated user.",
    ),
    destroy=extend_schema(
        summary="Delete an address",
        description=(
            "Deletes an address. If the deleted address was the default, "
            "the most recently created remaining address is automatically promoted to default."
        ),
    ),
)
class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).order_by('-is_default', '-created_at')

    @extend_schema(
        summary="Set an address as default",
        description="Marks this address as the user's default, unsetting any previous default.",
    )
    @action(detail=True, methods=['post'], url_path='set-default')
    def set_default(self, request, pk=None):
        address = self.get_object()
        address.is_default = True
        address.save(update_fields=['is_default'])
        return Response(AddressSerializer(address, context={'request': request}).data)

