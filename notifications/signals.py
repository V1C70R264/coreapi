from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from orders.models import Order
from .models import Notification, NotificationType

# (title, body-template) per status. body uses .format(order_number=...)
_STATUS_MESSAGES = {
    'confirmed': (
        'Order Confirmed',
        'Your order {order_number} has been confirmed.',
    ),
    'processing': (
        'Order Processing',
        'Your order {order_number} is being processed.',
    ),
    'shipped': (
        'Order Shipped',
        'Your order {order_number} has shipped.',
    ),
    'out_for_delivery': (
        'Out for Delivery',
        'Your order {order_number} is out for delivery.',
    ),
    'delivered': (
        'Order Delivered',
        'Your order {order_number} has been delivered. Enjoy!',
    ),
    'cancelled': (
        'Order Cancelled',
        'Your order {order_number} was cancelled.',
    ),
}


@receiver(pre_save, sender=Order)
def _stash_previous_status(sender, instance, **kwargs):
    """
    Runs right before every Order save. Records what the status was
    in the database *before* this save, so the post_save handler below
    can tell whether this save actually changed the status — Django
    gives post_save no built-in way to see the "old" value on its own.
    """
    if not instance.pk:
        # A brand-new order has no "previous" status.
        instance._previous_status = None
        return
    try:
        instance._previous_status = (
            Order.objects.only('status').get(pk=instance.pk).status
        )
    except Order.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Order)
def _notify_on_order_change(sender, instance, created, **kwargs):
    """
    Runs right after every Order save. Fires once when an order is
    first created, and again any time its status actually changes —
    regardless of *what* triggered the save (the staff transition
    endpoints, Django admin, a future management script). This is
    the whole point of using a signal instead of putting the
    notification logic inside OrderViewSet.
    """
    if created:
        Notification.objects.create(
            user=instance.customer,
            notification_type=NotificationType.ORDER_STATUS,
            title='Order Placed',
            body=f'Your order {instance.order_number} has been placed.',
            order=instance,
        )
        return

    previous_status = getattr(instance, '_previous_status', None)
    if previous_status is None or previous_status == instance.status:
        return  # nothing to report — this save didn't change status

    message = _STATUS_MESSAGES.get(instance.status)
    if message is None:
        return  # an unrecognized status value — don't guess at wording

    title, body_template = message
    Notification.objects.create(
        user=instance.customer,
        notification_type=NotificationType.ORDER_STATUS,
        title=title,
        body=body_template.format(order_number=instance.order_number),
        order=instance,
    )