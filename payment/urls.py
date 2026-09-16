from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import PaymentViewSet, InitiatePaymentView, FlutterwaveWebhookView

router = DefaultRouter()
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('payments/initiate/', InitiatePaymentView.as_view(), name='payment-initiate'),
    path('payments/webhook/flutterwave/', FlutterwaveWebhookView.as_view(), name='payment-webhook-flutterwave'),
] + router.urls