from django.db.models import F
from rest_framework.viewsets import ModelViewSet
from .serializers import CartSerializer, CartItemSerializer
from .models import Cart, CartItem
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view


@extend_schema(tags=["Cart"])
@extend_schema_view(
    list=extend_schema(
        summary="Retrieve my cart",
        description=(
            "Returns the cart belonging to the authenticated user "
            "along with its current items and total price."
        ),
    ),
    retrieve=extend_schema(
        summary="Retrieve my cart",
        description="Returns the authenticated user's cart and its current contents.",
    ),
    destroy=extend_schema(
        summary="Delete cart",
        description="Deletes the authenticated user's cart.",
    ),
)
class CartViewSet(ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]
    # No explicit create/update — a cart is created implicitly the
    # first time a CartItem is added (see CartItemViewSet.perform_create).
    http_method_names = ['get', 'delete', 'head']

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user).prefetch_related('items__product')

    def list(self, request, *args, **kwargs):
        # A user has exactly one cart, so GET /cart/ should return that
        # single object directly — not a paginated list. get_or_create
        # also means a brand-new user gets an empty cart object back
        # instead of an empty `results: []`.
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart = Cart.objects.prefetch_related('items__product').get(pk=cart.pk)
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @extend_schema(
        summary="Clear cart",
        description="Removes all items from the authenticated user's cart while keeping the cart itself.",
    )
    @action(detail=False, methods=['delete'], url_path='clear')
    def clear_cart(self, request):
        cart = Cart.objects.filter(user=request.user).first()

        if not cart:
            return Response(
                {"detail": "No cart found for the user."},
                status=status.HTTP_404_NOT_FOUND
            )

        cart.items.all().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Cart Items"])
@extend_schema_view(
    list=extend_schema(
        summary="List cart items",
        description="Returns the cart items belonging to the authenticated user.",
    ),
    retrieve=extend_schema(
        summary="Retrieve cart item",
        description="Returns a single cart item belonging to the authenticated user.",
    ),
    create=extend_schema(
        summary="Add product to cart",
        description=(
            "Adds a product to the authenticated user's cart. "
            "If the product is already in the cart, its quantity is increased."
        ),
    ),
    update=extend_schema(
        summary="Update cart item",
        description="Fully updates a cart item's quantity. The product cannot be changed.",
    ),
    partial_update=extend_schema(
        summary="Update cart item quantity",
        description="Updates the quantity of an existing cart item. The product cannot be changed.",
    ),
    destroy=extend_schema(
        summary="Remove cart item",
        description="Removes a product from the authenticated user's cart.",
    ),
)
class CartItemViewSet(ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CartItem.objects.filter(
            cart__user=self.request.user
        ).select_related('product', 'cart').order_by('-added_at')

    def perform_create(self, serializer):
        cart, created = Cart.objects.get_or_create(user=self.request.user)

        product = serializer.validated_data['product']
        quantity = serializer.validated_data['quantity']

        cart_item = CartItem.objects.filter(cart=cart, product=product).first()

        if not cart_item:
            serializer.save(cart=cart)
        else:
            # Atomic increment — avoids a lost update if two requests
            # add the same product to the cart at nearly the same time.
            CartItem.objects.filter(pk=cart_item.pk).update(
                quantity=F('quantity') + quantity
            )
            cart_item.refresh_from_db()
            serializer.instance = cart_item

    def perform_update(self, serializer):
        serializer.save(product=self.get_object().product)