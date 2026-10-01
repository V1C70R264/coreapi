from rest_framework import viewsets, permissions
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Promotion
from .serializers import PromotionSerializer


@extend_schema(tags=["Promotions"])
@extend_schema_view(
    list=extend_schema(
        summary="List active promotions",
        description="Returns currently active promotional banners, ordered for display.",
    ),
)
class PromotionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PromotionSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None  # the app needs the full set to build a carousel later

    def get_queryset(self):
        return Promotion.objects.filter(is_active=True)