
from .serializers import ProductSerializer, CategorySerializer
from .models import Product, Category
from rest_framework import viewsets, serializers
from rest_framework.filters import SearchFilter, OrderingFilter
from .pagination import ProductPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions
from .filters import ProductFilter 
from .permissions import IsSellerOrAdmin
from drf_spectacular.utils import extend_schema, extend_schema_view


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

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'price', 'created_at']
    #setting permissions for the product views 
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [IsSellerOrAdmin]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

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
    queryset = Category.objects.all()
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