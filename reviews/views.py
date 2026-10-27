from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from orders.models import OrderItem, OrderStatus
from products.models import Product
from .models import Review
from .serializers import ReviewSerializer


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user == request.user


@extend_schema(tags=["Reviews"])
@extend_schema_view(
    list=extend_schema(
        summary="List reviews",
        description="Returns reviews, optionally filtered by ?product=<id>.",
    ),
    create=extend_schema(
        summary="Create a review",
        description=(
            "Creates a review for a product. Only allowed if the authenticated "
            "user has a delivered order containing that product, and hasn't "
            "already reviewed it."
        ),
    ),
    update=extend_schema(
        summary="Update a review",
        description="Updates the authenticated user's own review.",
    ),
    partial_update=extend_schema(
        summary="Partially update a review",
        description="Updates one or more fields of the authenticated user's own review.",
    ),
    destroy=extend_schema(
        summary="Delete a review",
        description="Deletes the authenticated user's own review.",
    ),
)
class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    http_method_names = ['get', 'post', 'patch', 'delete', 'head']

    def get_queryset(self):
        queryset = Review.objects.select_related('user', 'product').all()
        product_id = self.request.query_params.get('product')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

    @extend_schema(
        summary="Check review eligibility",
        description=(
            "Returns whether the authenticated user can review the given product "
            "(has a delivered order for it and hasn't already reviewed it)."
        ),
    )
    @action(
        detail=False,
        methods=['get'],
        url_path='can-review',
        permission_classes=[permissions.IsAuthenticated],
    )
    def can_review(self, request):
        product_id = request.query_params.get('product')
        if not product_id:
            return Response(
                {'detail': "'product' query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            return Response(
                {'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND
            )

        has_delivered_purchase = OrderItem.objects.filter(
            order__customer=request.user,
            order__status=OrderStatus.DELIVERED,
            product=product,
        ).exists()

        already_reviewed = Review.objects.filter(
            user=request.user, product=product
        ).exists()

        return Response({
            'can_review': has_delivered_purchase and not already_reviewed,
            'has_purchased': has_delivered_purchase,
            'already_reviewed': already_reviewed,
        })
