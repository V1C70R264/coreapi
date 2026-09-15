import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    PROCESSING = 'processing', 'Processing'
    SHIPPED = 'shipped', 'Shipped'
    OUT_FOR_DELIVERY = 'out_for_delivery', 'Out for delivery'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'


class Order(models.Model):

    ALLOWED_TRANSITIONS = {
        OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
        OrderStatus.CONFIRMED: {OrderStatus.PROCESSING, OrderStatus.CANCELLED},
        OrderStatus.PROCESSING: {OrderStatus.SHIPPED},
        OrderStatus.SHIPPED: {OrderStatus.OUT_FOR_DELIVERY},
        OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.DELIVERED},
        OrderStatus.DELIVERED: set(),
        OrderStatus.CANCELLED: set(),
    }

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    order_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        blank=True,
    )


    # Optional reference to the saved address used, for convenience/
    # traceability. Nullable + SET_NULL so deleting a saved address
    # never breaks historical orders — the snapshot fields below are
    # the actual source of truth for what was shipped where.
    shipping_address = models.ForeignKey(
        'addresses.Address',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )

    # Snapshot of the address at the moment the order was placed —
    # same pattern as OrderItem snapshotting product_name/unit_price.
    recipient_name = models.CharField(max_length=255)
    recipient_phone = models.CharField(max_length=20)
    shipping_region = models.CharField(max_length=100)
    shipping_district = models.CharField(max_length=100)
    shipping_street_address = models.TextField()

    scheduled_delivery_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['customer', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    def _generate_order_number(self):
        today = timezone.now().strftime('%Y%m%d')
        return f"ORD-{today}-{uuid.uuid4().hex[:8].upper()}"

    def can_transition_to(self, new_status):
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    def transition_to(self, new_status):
        """
        Validates and applies a status transition. Raises ValueError
        with a human-readable message if the transition isn't allowed.
        Does not save — caller decides when/how to persist (so it can
        be combined with other changes, e.g. restocking, in one save).
        """
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Cannot transition from '{self.status}' to '{new_status}'."
            )
        self.status = new_status


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        related_name='items',
        on_delete=models.CASCADE,
    )

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
    )

    product_image_url = models.URLField(blank=True)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)