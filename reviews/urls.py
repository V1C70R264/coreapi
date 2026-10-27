from rest_framework.routers import DefaultRouter
from . import views
from .views import ReviewViewSet

router = DefaultRouter()
router.register(r'reviews', views.ReviewViewSet, basename='review') 
urlpatterns = router.urls