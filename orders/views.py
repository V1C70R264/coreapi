from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from rest_framework import viewsets
from django.db.models import F
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .serializers import OrderSerializer
from .pagination import OrderPagination
from .models import Order, OrderStatus
from products.models import Product
from drf_spectacular.utils import extend_schema, extend_schema_view


@extend_schema(tags=["Orders"])
@extend_schema_view(
    list=extend_schema(
        summary="List orders",
        description=(
            "Returns a paginated list of orders. "
            "Staff users can see all orders, while regular users can only see their own."
        ),
    ),
    retrieve=extend_schema(
        summary="Retrieve an order",
        description=(
            "Returns the details of a specific order. "
            "Staff users can retrieve any order, while regular users can only retrieve their own."
        ),
    ),
    create=extend_schema(
        summary="Create an order",
        description=(
            "Creates a new order for the authenticated user. "
            "The order will be created with a 'pending' status."
        ),
    ),
)
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    pagination_class = OrderPagination
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head']

    def get_queryset(self):
        qs = Order.objects.select_related('customer').prefetch_related('items__product')
        if self.request.user.is_staff:
            return qs
        return qs.filter(customer=self.request.user)

    def get_permissions(self):
        if self.action in ('confirm', 'process', 'ship', 'out_for_delivery', 'deliver'):
            return [IsAdminUser()]
        return super().get_permissions()

    @extend_schema(
        summary="Cancel an order",
        description=(
            "Cancels an order if it is in 'pending' or 'confirmed' status. "
            "Restocks the products in the order and updates the order status to 'cancelled'."
        ),
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()

        if order.status not in (OrderStatus.PENDING, OrderStatus.CONFIRMED):
            return Response(
                {'detail': f"Cannot cancel an order in '{order.status}' status."},
                status=400,
            )

        with transaction.atomic():
            for item in order.items.select_related('product'):
                Product.objects.filter(id=item.product_id).update(
                    stock_quantity=F('stock_quantity') + item.quantity
                )
            order.status = OrderStatus.CANCELLED
            order.save(update_fields=['status', 'updated_at'])

        return Response(OrderSerializer(order, context={'request': request}).data)

    def _apply_transition(self, request, pk, new_status):
        order = self.get_object()
        try:
            order.transition_to(new_status)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)

        order.save(update_fields=['status', 'updated_at'])
        return Response(OrderSerializer(order, context={'request': request}).data)

    @extend_schema(
        summary="Confirm an order",
        description=(
            "Confirms an order if it is in 'pending' status (staff only). "
            "Updates the order status to 'confirmed'."
        ),
    )
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        return self._apply_transition(request, pk, OrderStatus.CONFIRMED)

    @extend_schema(
        summary="Process an order",
        description=(
            "Moves an order to 'processing' if it is currently 'confirmed' (staff only)."
        ),
    )
    @action(detail=True, methods=['post'])
    def process(self, request, pk=None):
        return self._apply_transition(request, pk, OrderStatus.PROCESSING)

    @extend_schema(
        summary="Ship an order",
        description=(
            "Marks an order as 'shipped' if it is currently 'processing' (staff only)."
        ),
    )
    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        return self._apply_transition(request, pk, OrderStatus.SHIPPED)

    @extend_schema(
        summary="Mark an order as out for delivery",
        description=(
            "Marks an order as 'out for delivery' if it is currently 'shipped' (staff only)."
        ),
    )
    @action(detail=True, methods=['post'], url_path='out-for-delivery')
    def out_for_delivery(self, request, pk=None):
        return self._apply_transition(request, pk, OrderStatus.OUT_FOR_DELIVERY)

    @extend_schema(
        summary="Deliver an order",
        description=(
            "Marks an order as 'delivered' if it is currently 'out for delivery' (staff only)."
        ),
    )
    @action(detail=True, methods=['post'])
    def deliver(self, request, pk=None):
        return self._apply_transition(request, pk, OrderStatus.DELIVERED)