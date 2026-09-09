# urls for products app
from django.urls import path, include
from rest_framework import routers
from .views import ProductViewSet
from .views import CategoryViewSet

router = routers.DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
urlpatterns = [
    path('', include(router.urls)),
]