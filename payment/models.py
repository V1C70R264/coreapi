from django.db import models

import uuid
from django.db import models
from django.conf import settings

from orders.models import Order, OrderStatus


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    SUCCESSFUL = 'successful', 'Successful'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'


class PaymentGateway(models.TextChoices):
    FLUTTERWAVE = 'flutterwave', 'Flutterwave'


class Payment(models.Model):
    """
    Represents a single payment attempt against an order. An order can
    have multiple Payment rows over time (failed attempt, then a
    successful retry) — this table is an attempt log, not a 1:1 mirror
    of Order.
    """

    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name='payments',
    )

    # Our own reference, generated before redirecting to the gateway.
    # Used to look up the Payment row when the gateway calls back.
    tx_ref = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        blank=True,
    )

    # The gateway's own transaction identifier — only known after the
    # payment attempt completes, populated from the webhook/callback.
    gateway_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    gateway = models.CharField(
        max_length=20,
        choices=PaymentGateway.choices,
        default=PaymentGateway.FLUTTERWAVE,
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='TZS')

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g. 'card', 'mobile_money' — populated from gateway response.",
    )

    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.tx_ref} — {self.status}"

    def save(self, *args, **kwargs):
        if not self.tx_ref:
            self.tx_ref = self._generate_tx_ref()
        super().save(*args, **kwargs)

    def _generate_tx_ref(self):
        return f"PAY-{uuid.uuid4().hex[:16].upper()}"

    def mark_successful(self, gateway_transaction_id, payment_method='', paid_at=None):
        """
        Marks this payment successful and confirms the linked order.
        Caller is responsible for wrapping this in a transaction and
        for idempotency checks (see WebhookEvent) — this method itself
        does not re-check whether it's already been called.
        """
        from django.utils import timezone

        self.status = PaymentStatus.SUCCESSFUL
        self.gateway_transaction_id = gateway_transaction_id
        self.payment_method = payment_method
        self.paid_at = paid_at or timezone.now()
        self.save(update_fields=[
            'status', 'gateway_transaction_id', 'payment_method', 'paid_at', 'updated_at'
        ])

        if self.order.status == OrderStatus.PENDING:
            self.order.transition_to(OrderStatus.CONFIRMED)
            self.order.save(update_fields=['status', 'updated_at'])

    def mark_failed(self, gateway_transaction_id=''):
        self.status = PaymentStatus.FAILED
        if gateway_transaction_id:
            self.gateway_transaction_id = gateway_transaction_id
        self.save(update_fields=['status', 'gateway_transaction_id', 'updated_at'])


class WebhookEvent(models.Model):
    """
    Records every webhook event received, keyed by the gateway's own
    event identifier. The unique constraint on (gateway, event_id) is
    the actual idempotency guarantee — if the gateway retries delivery
    of the same event, the second insert fails and we know to skip
    reprocessing, regardless of any application-level check.
    """

    gateway = models.CharField(max_length=20, choices=PaymentGateway.choices)
    event_id = models.CharField(max_length=150)
    payload = models.JSONField()
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['gateway', 'event_id'],
                name='unique_webhook_event_per_gateway',
            )
        ]
        indexes = [
            models.Index(fields=['gateway', 'event_id']),
        ]

    def __str__(self):
        return f"{self.gateway}:{self.event_id}"
