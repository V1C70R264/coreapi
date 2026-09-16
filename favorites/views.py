from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Favorite
from .serializers import FavoriteSerializer
from products.models import Product


@extend_schema(tags=["Favorites"])
@extend_schema_view(
    list=extend_schema(summary="List favorites", description="Returns the authenticated user's favorited products."),
    create=extend_schema(summary="Add a favorite", description="Adds a product to the authenticated user's favorites."),
    destroy=extend_schema(summary="Remove a favorite", description="Removes a product from favorites by favorite id."),
)
class FavoriteViewSet(viewsets.ModelViewSet):
    serializer_class = FavoriteSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head']

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user).select_related('product')

    @extend_schema(
        summary="Toggle a favorite",
        description="Adds the product to favorites if not already favorited, or removes it if it is.",
    )
    @action(detail=False, methods=['post'])
    def toggle(self, request):
        product_id = request.data.get('product')
        if not product_id:
            return Response({'detail': "'product' is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'detail': "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        favorite = Favorite.objects.filter(user=request.user, product=product).first()
        if favorite:
            favorite.delete()
            return Response({'favorited': False}, status=status.HTTP_200_OK)

        Favorite.objects.create(user=request.user, product=product)
        return Response({'favorited': True}, status=status.HTTP_201_CREATED)