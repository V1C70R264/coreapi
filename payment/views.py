import logging
from django.conf import settings
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_spectacular.utils import extend_schema

from .models import Payment, WebhookEvent, PaymentGateway
from .serializers import PaymentInitiateSerializer, PaymentSerializer
from .gateways import FlutterwaveGateway, FlutterwaveError

logger = logging.getLogger(__name__)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only — payments are created via the initiate endpoint and
    updated only by the webhook, never directly by clients.
    """
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payment.objects.filter(order__customer=self.request.user)


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Initiate payment for an order",
        description=(
            "Creates a payment attempt for the given order and returns a "
            "hosted checkout link the client should redirect the user to."
        ),
        request=PaymentInitiateSerializer,
    )
    def post(self, request):
        serializer = PaymentInitiateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        order = serializer.order

        payment = Payment.objects.create(
            order=order,
            amount=order.total_amount,
            currency='TZS',
            gateway=PaymentGateway.FLUTTERWAVE,
        )

        gateway = FlutterwaveGateway()
        try:
            checkout_url = gateway.initiate_payment(
                tx_ref=payment.tx_ref,
                amount=payment.amount,
                currency=payment.currency,
                customer_email=request.user.email,
                customer_name=request.user.get_full_name() or request.user.username,
                redirect_url=settings.PAYMENT_REDIRECT_URL,
            )
        except FlutterwaveError as e:
            payment.mark_failed()
            return Response({'detail': str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'payment_id': payment.id,
            'tx_ref': payment.tx_ref,
            'checkout_url': checkout_url,
        }, status=status.HTTP_201_CREATED)


class FlutterwaveWebhookView(APIView):
    """
    Public endpoint — Flutterwave calls this directly, no user auth.
    Security relies entirely on signature verification below, plus a
    server-to-server verify call before trusting anything in the payload.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.headers.get('verif-hash')
        if not signature or signature != settings.FLUTTERWAVE_WEBHOOK_SECRET_HASH:
            logger.warning("Rejected webhook: invalid or missing signature")
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        payload = request.data
        event_id = str(payload.get('data', {}).get('id') or payload.get('id') or '')
        if not event_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            event, created = WebhookEvent.objects.get_or_create(
                gateway=PaymentGateway.FLUTTERWAVE,
                event_id=event_id,
                defaults={'payload': payload},
            )
            if not created:
                # Already seen this exact event — acknowledge without
                # reprocessing, so the gateway stops retrying.
                return Response(status=status.HTTP_200_OK)

            tx_ref = payload.get('data', {}).get('tx_ref')
            gateway_transaction_id = payload.get('data', {}).get('id')

            try:
                payment = Payment.objects.select_for_update().get(tx_ref=tx_ref)
            except Payment.DoesNotExist:
                logger.error(f"Webhook for unknown tx_ref: {tx_ref}")
                return Response(status=status.HTTP_200_OK)  # ack anyway — nothing to retry

            if payment.status == 'successful':
                # Already processed via an earlier event or race — no-op.
                return Response(status=status.HTTP_200_OK)

            # Don't trust the webhook payload's status/amount directly —
            # verify server-to-server against Flutterwave's own API.
            gw = FlutterwaveGateway()
            try:
                verified = gw.verify_transaction(gateway_transaction_id)
            except FlutterwaveError as e:
                logger.error(f"Verification failed for {tx_ref}: {e}")
                return Response(status=status.HTTP_502_BAD_GATEWAY)

            if (
                verified.get('status') == 'successful'
                and verified.get('tx_ref') == payment.tx_ref
                and Decimal(str(verified.get('amount'))) == payment.amount
                and verified.get('currency') == payment.currency
            ):
                payment.mark_successful(
                    gateway_transaction_id=gateway_transaction_id,
                    payment_method=verified.get('payment_type', ''),
                )
            else:
                payment.mark_failed(gateway_transaction_id=gateway_transaction_id)

            event.processed_at = timezone.now()
            event.save(update_fields=['processed_at'])

        return Response(status=status.HTTP_200_OK)
