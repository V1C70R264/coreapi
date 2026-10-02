from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    ORDER_STATUS = 'order_status', 'Order status'
    PROMOTION = 'promotion', 'Promotion'  # not wired yet — reserved for the opt-in follow-up


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.ORDER_STATUS,
    )
    title = models.CharField(max_length=150)
    body = models.TextField()

    # Nullable + SET_NULL so a deleted order never breaks a historical
    # notification — same pattern as Order.shipping_address.
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications',
    )

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user} — {self.title}"
