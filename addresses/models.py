from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Address(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='addresses',
    )

    label = models.CharField(
        max_length=50,
        blank=True,
        help_text="Optional label, e.g. 'Home', 'Office'.",
    )

    full_name = models.CharField(max_length=255)

    phone_number = models.CharField(
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?\d{9,15}$',
                message="Enter a valid phone number (digits only, optional leading +).",
            )
        ],
    )

    region = models.CharField(max_length=100)
    district = models.CharField(max_length=100)
    street_address = models.TextField()

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_default']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_default=True),
                name='unique_default_address_per_user',
            )
        ]

    def __str__(self):
        return f"{self.full_name} — {self.district}, {self.region}"

    def save(self, *args, **kwargs):
        # First address for this user always becomes the default —
        # guarantees a user with >=1 address always has exactly one default.
        is_new = self.pk is None
        if is_new and not Address.objects.filter(user=self.user).exists():
            self.is_default = True

        if self.is_default:
            Address.objects.filter(
                user=self.user, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)


@receiver(post_delete, sender=Address)
def promote_new_default_on_delete(sender, instance, **kwargs):
    """
    If the deleted address was the user's default, and other addresses
    still exist, promote the most recently created one to default.
    Fires on both single-instance and bulk queryset deletes, since
    Django's post_delete signal runs per-object in both cases.
    """
    if not instance.is_default:
        return

    replacement = (
        Address.objects.filter(user_id=instance.user_id)
        .order_by('-created_at')
        .first()
    )
    if replacement is not None:
        replacement.is_default = True
        replacement.save(update_fields=['is_default'])