from rest_framework.routers import DefaultRouter
from addresses.views import AddressViewSet

router = DefaultRouter()
router.register(r'addresses', AddressViewSet, basename='address')
urlpatterns = router.urls