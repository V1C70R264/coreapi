from django.test import TestCase
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from addresses.models import Address
from products.models import Product, Category
from orders.models import Order, OrderStatus
from .models import Payment, WebhookEvent, PaymentStatus
from .gateways import FlutterwaveError

User = get_user_model()


class PaymentInitiationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', email='buyer@test.com', password='pw')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category,
        )
        self.address = Address.objects.create(
            user=self.user, full_name='Buyer', phone_number='+255712345678',
            region='Dar es Salaam', district='Ilala', street_address='1 St',
        )
        resp = self.client.post('/api/v1/orders/', {
            'shipping_address_id': self.address.id,
            'items': [{'product': self.product.id, 'quantity': 1}],
        }, format='json')
        self.order_id = resp.data['id']

    @patch('payment.views.FlutterwaveGateway.initiate_payment')
    def test_initiate_payment_creates_pending_payment_and_returns_link(self, mock_initiate):
        mock_initiate.return_value = 'https://checkout.flutterwave.com/fake-link'

        resp = self.client.post('/api/v1/payments/initiate/', {
            'order_id': self.order_id,
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['checkout_url'], 'https://checkout.flutterwave.com/fake-link')

        payment = Payment.objects.get(id=resp.data['payment_id'])
        self.assertEqual(payment.status, PaymentStatus.PENDING)
        self.assertEqual(payment.amount, Decimal('1200000.00'))
        self.assertTrue(payment.tx_ref.startswith('PAY-'))

    @patch('payment.views.FlutterwaveGateway.initiate_payment')
    def test_gateway_failure_marks_payment_failed(self, mock_initiate):
        mock_initiate.side_effect = FlutterwaveError("Gateway unreachable")

        resp = self.client.post('/api/v1/payments/initiate/', {
            'order_id': self.order_id,
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_502_BAD_GATEWAY)
        payment = Payment.objects.get(order_id=self.order_id)
        self.assertEqual(payment.status, PaymentStatus.FAILED)

    def test_cannot_initiate_payment_for_nonexistent_order(self):
        resp = self.client.post('/api/v1/payments/initiate/', {
            'order_id': 99999,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_initiate_payment_for_confirmed_order(self):
        order = Order.objects.get(id=self.order_id)
        order.transition_to(OrderStatus.CONFIRMED)
        order.save(update_fields=['status'])

        resp = self.client.post('/api/v1/payments/initiate/', {
            'order_id': self.order_id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_initiate_payment_for_another_users_order(self):
        other_user = User.objects.create_user(username='other', email='other@test.com', password='pw')
        other_client = APIClient()
        other_client.force_authenticate(other_user)

        resp = other_client.post('/api/v1/payments/initiate/', {
            'order_id': self.order_id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class FlutterwaveWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', email='buyer@test.com', password='pw')
        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category,
        )
        self.address = Address.objects.create(
            user=self.user, full_name='Buyer', phone_number='+255712345678',
            region='Dar es Salaam', district='Ilala', street_address='1 St',
        )
        self.order = Order.objects.create(
            customer=self.user, total_amount=Decimal('1200000.00'),
            scheduled_delivery_date='2026-09-20',
            shipping_address=self.address,
            recipient_name='Buyer', recipient_phone='+255712345678',
            shipping_region='Dar es Salaam', shipping_district='Ilala',
            shipping_street_address='1 St',
        )
        self.payment = Payment.objects.create(
            order=self.order, amount=Decimal('1200000.00'), currency='TZS',
        )
        self.client = APIClient()

        self.webhook_payload = {
            'data': {
                'id': 998877,
                'tx_ref': self.payment.tx_ref,
                'status': 'successful',
                'amount': 1200000.00,
                'currency': 'TZS',
            }
        }

    def _post_webhook(self, payload, signature='correct-secret'):
        with self.settings(FLUTTERWAVE_WEBHOOK_SECRET_HASH='correct-secret'):
            return self.client.post(
                '/api/v1/payments/webhook/flutterwave/',
                payload,
                format='json',
                HTTP_VERIF_HASH=signature,
            )

    def test_webhook_without_valid_signature_rejected(self):
        resp = self._post_webhook(self.webhook_payload, signature='wrong-secret')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.PENDING)  # untouched

    @patch('payment.views.FlutterwaveGateway.verify_transaction')
    def test_valid_webhook_marks_payment_successful_and_confirms_order(self, mock_verify):
        mock_verify.return_value = {
            'status': 'successful',
            'tx_ref': self.payment.tx_ref,
            'amount': 1200000.00,
            'currency': 'TZS',
            'payment_type': 'card',
        }

        resp = self._post_webhook(self.webhook_payload)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.SUCCESSFUL)
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)

    @patch('payment.views.FlutterwaveGateway.verify_transaction')
    def test_duplicate_webhook_event_is_not_reprocessed(self, mock_verify):
        mock_verify.return_value = {
            'status': 'successful',
            'tx_ref': self.payment.tx_ref,
            'amount': 1200000.00,
            'currency': 'TZS',
            'payment_type': 'card',
        }

        resp1 = self._post_webhook(self.webhook_payload)
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_verify.call_count, 1)

        resp2 = self._post_webhook(self.webhook_payload)  # same event_id
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(mock_verify.call_count, 1)  # not called again

        self.assertEqual(WebhookEvent.objects.count(), 1)

    @patch('payment.views.FlutterwaveGateway.verify_transaction')
    def test_amount_mismatch_marks_payment_failed_not_successful(self, mock_verify):
        # Webhook claims success, but server-to-server verify disagrees
        # on amount — should NOT be trusted; payment marked failed.
        mock_verify.return_value = {
            'status': 'successful',
            'tx_ref': self.payment.tx_ref,
            'amount': 1.00,  # tampered/mismatched amount
            'currency': 'TZS',
            'payment_type': 'card',
        }

        resp = self._post_webhook(self.webhook_payload)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentStatus.FAILED)
        self.assertEqual(self.order.status, OrderStatus.PENDING)  # not confirmed

    def test_webhook_for_unknown_tx_ref_acknowledged_without_crash(self):
        bad_payload = {
            'data': {'id': 555, 'tx_ref': 'PAY-DOESNOTEXIST', 'status': 'successful', 'amount': 1, 'currency': 'TZS'}
        }
        resp = self._post_webhook(bad_payload)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

# Create your tests here.
