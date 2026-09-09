from django.db import models
from django.conf import settings

class Product(models.Model):
    name = models.CharField(max_length=255)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='products', null=True, blank=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField()
    category = models.ForeignKey('Category', on_delete=models.PROTECT, related_name='products')
    image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        old_image = None

        if self.pk:
            old_product = Product.objects.get(pk=self.pk)
            old_image = old_product.image

        super().save(*args, **kwargs)

        if old_image and old_image.name != self.image.name:
            old_image.delete(save=False)

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete(save=False)

        return super().delete(*args, **kwargs)

# category model
class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name
