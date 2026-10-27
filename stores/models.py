from django.conf import settings
from django.db import models

class StoreStatus(models.TextChoices):
    PENDING = 'pending', 'Pending review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'

class Store(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='store',
    )
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='stores/', blank=True, null=True)
    
    # Where the store is in the application process.
    status = models.CharField(
        max_length=10,
        choices=StoreStatus.choices,
        default=StoreStatus.PENDING,
    )
    # Shown to the seller when rejected, so they know what to fix.
    rejection_reason = models.TextField(blank=True)

    # Separate switch for hiding an approved store temporarily.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
