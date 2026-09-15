# orders/tests.py
import threading
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from addresses.models import Address

from products.models import Product, Category
from .models import Order, OrderStatus

User = get_user_model()


class OrderCreationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='pw', email='buyer1@test.com')
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

    def test_create_order_deducts_stock(self):
        resp = self.client.post('/api/v1/orders/', {
            'shipping_address_id': self.address.id,
            'items': [{'product': self.product.id, 'quantity': 2}]
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)

    def test_create_order_fails_on_insufficient_stock(self):
        resp = self.client.post('/api/v1/orders/', {
            'shipping_address_id': self.address.id,
            'items': [{'product': self.product.id, 'quantity': 99}]
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)  # untouched

    def test_order_number_generated_and_fits_column(self):
        resp = self.client.post('/api/v1/orders/', {
            'shipping_address_id': self.address.id,
            'items': [{'product': self.product.id, 'quantity': 1}]
        }, format='json')
        order = Order.objects.get(id=resp.data['id'])
        self.assertTrue(order.order_number.startswith('ORD-'))
        self.assertLessEqual(len(order.order_number), 32)

    def test_patch_is_blocked(self):
        order = Order.objects.create(
            customer=self.user, total_amount=0,
            scheduled_delivery_date='2026-09-20',
            recipient_name='Buyer', recipient_phone='+255712345678',
            shipping_region='Dar es Salaam', shipping_district='Ilala',
            shipping_street_address='1 St',
        )
        resp = self.client.patch(f'/api/v1/orders/{order.id}/', {'status': 'confirmed'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class OrderCancelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', password='pw', email='cancelbuyer@test.com')
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
        create_resp = self.client.post('/api/v1/orders/', {
            'shipping_address_id': self.address.id,
            'items': [{'product': self.product.id, 'quantity': 2}]
        }, format='json')
        self.order_id = create_resp.data['id']

    def test_cancel_restocks_items(self):
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)  # after order

        resp = self.client.post(f'/api/v1/orders/{self.order_id}/cancel/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)  # restocked

    def test_double_cancel_rejected_and_does_not_double_restock(self):
        self.client.post(f'/api/v1/orders/{self.order_id}/cancel/')
        resp = self.client.post(f'/api/v1/orders/{self.order_id}/cancel/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 5)  # not 7


class OrderConcurrencyTests(TransactionTestCase):
    """
    TransactionTestCase (not TestCase) is required here — TestCase wraps
    each test in a single DB transaction that never actually commits,
    so separate threads can't see each other's in-flight changes and
    select_for_update() has nothing real to contend over.
    """

    def setUp(self):
        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='Last Unit Phone', price=Decimal('1200000.00'),
            stock_quantity=1, category=self.category,
        )
        self.user_a = User.objects.create_user(username='buyer_a', email='buyer_a@test.com', password='pw')
        self.user_b = User.objects.create_user(username='buyer_b', email='buyer_b@test.com', password='pw')
        self.address_a = Address.objects.create(
            user=self.user_a, full_name='A', phone_number='+255712340001',
            region='Dar', district='Ilala', street_address='1 St',
        )
        self.address_b = Address.objects.create(
            user=self.user_b, full_name='B', phone_number='+255712340002',
            region='Dar', district='Kinondoni', street_address='2 St',
        )

    def test_two_simultaneous_orders_cannot_both_succeed(self):
        results = {}

        def place_order(username, key, address_id):
            client = APIClient()
            user = User.objects.get(username=username)
            client.force_authenticate(user)
            resp = client.post('/api/v1/orders/', {
                'shipping_address_id': address_id,
                'items': [{'product': self.product.id, 'quantity': 1}]
            }, format='json')
            results[key] = resp.status_code

        t1 = threading.Thread(target=place_order, args=('buyer_a', 'a', self.address_a.id))
        t2 = threading.Thread(target=place_order, args=('buyer_b', 'b', self.address_b.id))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        statuses = list(results.values())

        # Exactly one should succeed (201), the other should fail (400)
        self.assertEqual(statuses.count(status.HTTP_201_CREATED), 1)
        self.assertEqual(statuses.count(status.HTTP_400_BAD_REQUEST), 1)

        # And stock must never go negative
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 0)


class OrderTransitionTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='buyer', email='buyer@test.com', password='pw'
        )
        self.staff = User.objects.create_user(
            username='staff', email='staff@test.com', password='pw', is_staff=True
        )
        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category,
        )
        self.address = Address.objects.create(
            user=self.customer, full_name='Buyer', phone_number='+255712345678',
            region='Dar es Salaam', district='Ilala', street_address='1 St',
        )
        self.client = APIClient()
        self.client.force_authenticate(self.customer)
        resp = self.client.post('/api/v1/orders/', {
            'shipping_address_id': self.address.id,
            'items': [{'product': self.product.id, 'quantity': 1}]
        }, format='json')
        self.order_id = resp.data['id']

    def test_customer_cannot_confirm_order(self):
        resp = self.client.post(f'/api/v1/orders/{self.order_id}/confirm/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_confirm_then_process_then_ship_then_deliver(self):
        staff_client = APIClient()
        staff_client.force_authenticate(self.staff)

        for action, expected_status in [
            ('confirm', 'confirmed'),
            ('process', 'processing'),
            ('ship', 'shipped'),
            ('out-for-delivery', 'out_for_delivery'),
            ('deliver', 'delivered'),
        ]:
            resp = staff_client.post(f'/api/v1/orders/{self.order_id}/{action}/')
            self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
            self.assertEqual(resp.data['status'], expected_status)

    def test_cannot_skip_a_transition(self):
        staff_client = APIClient()
        staff_client.force_authenticate(self.staff)
        resp = staff_client.post(f'/api/v1/orders/{self.order_id}/ship/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_transition_from_terminal_state(self):
        staff_client = APIClient()
        staff_client.force_authenticate(self.staff)
        self.client.post(f'/api/v1/orders/{self.order_id}/cancel/')
        resp = staff_client.post(f'/api/v1/orders/{self.order_id}/confirm/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class OrderShippingAddressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer', email='buyer@test.com', password='pw'
        )
        self.other_user = User.objects.create_user(
            username='other', email='other@test.com', password='pw'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category,
        )
        self.address = Address.objects.create(
            user=self.user, full_name='Victor', phone_number='+255712345678',
            region='Dar es Salaam', district='Ilala', street_address='123 Main St',
        )

    def test_order_snapshots_address_fields(self):
        resp = self.client.post('/api/v1/orders/', {
            'shipping_address_id': self.address.id,
            'items': [{'product': self.product.id, 'quantity': 1}],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['recipient_name'], 'Victor')
        self.assertEqual(resp.data['shipping_district'], 'Ilala')

    def test_cannot_use_another_users_address(self):
        other_address = Address.objects.create(
            user=self.other_user, full_name='Other', phone_number='+255712345679',
            region='Dar es Salaam', district='Kinondoni', street_address='456 Other St',
        )
        resp = self.client.post('/api/v1/orders/', {
            'shipping_address_id': other_address.id,
            'items': [{'product': self.product.id, 'quantity': 1}],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_order_survives_address_deletion(self):
        resp = self.client.post('/api/v1/orders/', {
            'shipping_address_id': self.address.id,
            'items': [{'product': self.product.id, 'quantity': 1}],
        }, format='json')
        order_id = resp.data['id']

        self.address.delete()

        resp = self.client.get(f'/api/v1/orders/{order_id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['recipient_name'], 'Victor')  # snapshot survives