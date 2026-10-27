from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'category', 'price', 'stock_quantity', 'created_at')
    list_filter = ('category',)
    search_fields = ('name', 'seller__username')
    # A lookup box instead of a dropdown of every user.
    raw_id_fields = ('seller',)
    list_select_related = ('seller', 'category')