from django.db import IntegrityError, transaction
from django.db.models import Count, IntegerField, OuterRef, Subquery
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from products.models import Product
from products.pagination import ProductPagination
from products.serializers import ProductSerializer
from .models import Store, StoreStatus
from .serializers import (
    MyStoreSerializer,
    StoreApplicationSerializer,
    StoreSerializer,
)


@extend_schema(tags=["Stores"])
@extend_schema_view(
    list=extend_schema(
        summary="List stores",
        description="Returns approved, active stores that have listed at least one product, searchable by name.",
    ),
    retrieve=extend_schema(
        summary="Retrieve a store",
        description="Returns a single approved store by id.",
    ),
)
class StoreViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StoreSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = ProductPagination
    filter_backends = [SearchFilter]
    search_fields = ['name']

    def get_queryset(self):
        product_counts = (
            Product.objects
            .filter(seller=OuterRef('owner_id'))
            .order_by()
            .values('seller')
            .annotate(total=Count('id'))
            .values('total')
        )
        return (
            Store.objects
            .filter(
                status=StoreStatus.APPROVED,
                is_active=True,
                owner_id__in=Product.objects.values('seller'),
            )
            .annotate(
                product_count=Subquery(product_counts, output_field=IntegerField())
            )
            .order_by('-product_count', 'id')
        )

    @extend_schema(
        summary="Products from a store",
        description="Returns a paginated list of the given approved store's products.",
    )
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        store = self.get_object()
        queryset = Product.objects.filter(seller=store.owner).order_by('-created_at')

        page = self.paginate_queryset(queryset)
        serializer = ProductSerializer(
            page, many=True, context=self.get_serializer_context()
        )
        return self.get_paginated_response(serializer.data)

    @extend_schema(
        summary="My store",
        description="Returns the authenticated user's own store in any status, or 404 if they have not applied.",
        responses=MyStoreSerializer,
    )
    @action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def mine(self, request):
        store = Store.objects.filter(owner=request.user).first()
        if store is None:
            return Response(
                {'detail': 'You have not applied for a store.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(MyStoreSerializer(store).data)

    @extend_schema(
        summary="Apply for a store",
        description=(
            "Submits a store application for review. A user who was rejected "
            "can apply again with updated details."
        ),
        request=StoreApplicationSerializer,
        responses=MyStoreSerializer,
    )
    @action(
        detail=False,
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def apply(self, request):
        existing = Store.objects.filter(owner=request.user).first()

        if existing and existing.status != StoreStatus.REJECTED:
            return Response(
                {'detail': 'You already have a store application.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Passing the rejected store as the instance turns this into an
        # update, and keeps its own name from failing the uniqueness check.
        serializer = StoreApplicationSerializer(instance=existing, data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                store = serializer.save(
                    owner=request.user,
                    status=StoreStatus.PENDING,
                    rejection_reason='',
                )
        except IntegrityError:
            # Two applications from the same user at the same moment.
            return Response(
                {'detail': 'You already have a store application.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(MyStoreSerializer(store).data, status=status.HTTP_201_CREATED)