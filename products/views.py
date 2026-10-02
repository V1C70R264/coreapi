from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from .serializers import ProductSerializer, CategorySerializer
from .models import Product, Category
from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from .pagination import ProductPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions
from .filters import ProductFilter
from .permissions import IsSellerOrAdmin
from drf_spectacular.utils import extend_schema, extend_schema_view
from orders.models import OrderItem


@extend_schema(tags=["Products"])
@extend_schema_view(
    list=extend_schema(
        summary="List products",
        description=(
            "Returns a paginated list of products. "
            "Products can be filtered by category and price range, "
            "searched by name or description, and ordered by name, price, or creation date."
        ),
    ),
    retrieve=extend_schema(
        summary="Retrieve a product",
        description="Returns a single product by its ID.",
    ),
    create=extend_schema(
        summary="Create a product",
        description=(
            "Creates a new product. "
            "The seller is automatically assigned from the authenticated user."
        ),
    ),
    update=extend_schema(
        summary="Update a product",
        description=(
            "Fully updates a product. "
            "Only the product owner or an administrator can perform this operation."
        ),
    ),
    partial_update=extend_schema(
        summary="Partially update a product",
        description=(
            "Updates selected product fields. "
            "Only the product owner or an administrator can perform this operation."
        ),
    ),
    destroy=extend_schema(
        summary="Delete a product",
        description=(
            "Deletes a product. "
            "Only the product owner or an administrator can perform this operation."
        ),
    ),
)
class ProductViewSet(viewsets.ModelViewSet):

    # queryset = Product.objects.all()
    queryset = Product.objects.all().order_by('-created_at')
    serializer_class = ProductSerializer
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'created_at']
    #setting permissions for the product views 
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'trending', 'new_sellers']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsSellerOrAdmin]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    @extend_schema(
        summary="Trending products",
        description="Returns products ranked by total units sold in the last 7 days.",
    )
    @action(detail=False, methods=['get'])
    def trending(self, request):
        since = timezone.now() - timedelta(days=7)

        trending_product_ids = (
            OrderItem.objects
            .filter(order__created_at__gte=since)
            .exclude(order__status='cancelled')
            .values('product_id')
            .annotate(units_sold=Sum('quantity'))
            .order_by('-units_sold')
            .values_list('product_id', flat=True)
        )

        # Preserve the units_sold ranking order — a plain .filter(id__in=...)
        # would return results in the database's default order, not by
        # popularity, so we re-fetch in the exact ranked sequence instead.
        products_by_id = {
            p.id: p for p in Product.objects.filter(id__in=trending_product_ids)
        }
        ordered_products = [
            products_by_id[pid] for pid in trending_product_ids if pid in products_by_id
        ]

        page = self.paginate_queryset(ordered_products)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Products from new sellers",
        description="Returns products from sellers whose account was created in the last 90 days.",
    )
    @action(detail=False, methods=['get'], url_path='new-sellers')
    def new_sellers(self, request):
        since = timezone.now() - timedelta(days=90)

        queryset = (
            Product.objects
            .filter(seller__date_joined__gte=since)
            .order_by('-created_at')
        )

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


@extend_schema(tags=["Categories"])
@extend_schema_view(
    list=extend_schema(
        summary="List categories",
        description="Returns a list of all product categories.",
    ),
    retrieve=extend_schema(
        summary="Retrieve a category",
        description="Returns a single category by its ID.",
    ),
    create=extend_schema(
        summary="Create a category",
        description="Creates a new product category. Only administrators can perform this operation.",
    ),
    update=extend_schema(
        summary="Update a category",
        description="Fully updates a product category. Only administrators can perform this operation.",
    ),
    partial_update=extend_schema(
        summary="Partially update a category",
        description="Updates selected product category fields. Only administrators can perform this operation.",
    ),
    destroy=extend_schema(
        summary="Delete a category",
        description="Deletes a product category. Only administrators can perform this operation.",
    ),
)
class CategoryViewSet(viewsets.ModelViewSet):
    # queryset = Category.objects.all()
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAdminUser]

        return [permission() for permission in permission_classes]


    def perform_destroy(self, instance):
        if instance.products.exists():
            raise serializers.ValidationError("Cannot delete category with associated products.")
        instance.delete()