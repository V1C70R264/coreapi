
from django_filters import rest_framework as django_filter
from .models import Product
class ProductFilter(django_filter.FilterSet):
    """
    Filter class for the Product model.
    Allows filtering products based on category, price range, and availability.
    """
    min_price = django_filter.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = django_filter.NumberFilter(field_name="price", lookup_expr='lte')
    in_stock = django_filter.BooleanFilter(method='filter_in_stock')

    def filter_in_stock(self, queryset, name, value):
        """
        Custom filter method to filter products based on stock availability.
        """
        if value:
            return queryset.filter(stock_quantity__gt=0)
        return queryset.filter(stock_quantity=0)

    class Meta:
        model = Product
        fields = ['category', 'min_price', 'max_price', 'in_stock']