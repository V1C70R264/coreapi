from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from products.models import Product, Category
from .models import Cart, CartItem

User = get_user_model()


class CartItemCreationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', email='buyer@test.com', password='pw')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', description='A phone', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category,
        )

    def test_adding_product_creates_cart_automatically(self):
        self.assertFalse(Cart.objects.filter(user=self.user).exists())
        resp = self.client.post('/api/v1/cart-items/', {'product': self.product.id, 'quantity': 2}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(Cart.objects.filter(user=self.user).exists())

    def test_adding_same_product_twice_increments_quantity(self):
        self.client.post('/api/v1/cart-items/', {'product': self.product.id, 'quantity': 2}, format='json')
        resp = self.client.post('/api/v1/cart-items/', {'product': self.product.id, 'quantity': 1}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(CartItem.objects.filter(cart__user=self.user).count(), 1)  # one row, not two
        item = CartItem.objects.get(cart__user=self.user, product=self.product)
        self.assertEqual(item.quantity, 3)

    def test_cannot_add_out_of_stock_product(self):
        self.product.stock_quantity = 0
        self.product.save(update_fields=['stock_quantity'])

        resp = self.client.post('/api/v1/cart-items/', {'product': self.product.id, 'quantity': 1}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_add_more_than_available_stock(self):
        resp = self.client.post('/api/v1/cart-items/', {'product': self.product.id, 'quantity': 99}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_add_quantity_less_than_one(self):
        resp = self.client.post('/api/v1/cart-items/', {'product': self.product.id, 'quantity': 0}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class CartItemUpdateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer2', email='buyer2@test.com', password='pw')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', description='A phone', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category,
        )
        self.other_product = Product.objects.create(
            name='Samsung S24', description='Another phone', price=Decimal('1000000.00'),
            stock_quantity=5, category=self.category,
        )
        resp = self.client.post('/api/v1/cart-items/', {'product': self.product.id, 'quantity': 2}, format='json')
        self.item_id = resp.data['id']

    def test_update_quantity(self):
        resp = self.client.patch(f'/api/v1/cart-items/{self.item_id}/', {'quantity': 4}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        item = CartItem.objects.get(id=self.item_id)
        self.assertEqual(item.quantity, 4)

    def test_cannot_update_quantity_beyond_stock(self):
        resp = self.client.patch(f'/api/v1/cart-items/{self.item_id}/', {'quantity': 99}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_product_cannot_be_changed_on_update(self):
        resp = self.client.patch(
            f'/api/v1/cart-items/{self.item_id}/',
            {'product': self.other_product.id, 'quantity': 1},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        item = CartItem.objects.get(id=self.item_id)
        self.assertEqual(item.product, self.product)  # unchanged


class CartOwnershipTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='buyer_a', email='buyer_a@test.com', password='pw')
        self.user_b = User.objects.create_user(username='buyer_b', email='buyer_b@test.com', password='pw')
        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', description='A phone', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category,
        )

        self.client_a = APIClient()
        self.client_a.force_authenticate(self.user_a)
        resp = self.client_a.post('/api/v1/cart-items/', {'product': self.product.id, 'quantity': 1}, format='json')
        self.item_id = resp.data['id']

        self.client_b = APIClient()
        self.client_b.force_authenticate(self.user_b)

    def test_cannot_see_another_users_cart_items(self):
        resp = self.client_b.get('/api/v1/cart-items/')
        ids = [item['id'] for item in resp.data['results']] if 'results' in resp.data else [i['id'] for i in resp.data]
        self.assertNotIn(self.item_id, ids)

    def test_cannot_update_another_users_cart_item(self):
        resp = self.client_b.patch(f'/api/v1/cart-items/{self.item_id}/', {'quantity': 3}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_another_users_cart_item(self):
        resp = self.client_b.delete(f'/api/v1/cart-items/{self.item_id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(CartItem.objects.filter(id=self.item_id).exists())


class CartClearAndTotalsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer3', email='buyer3@test.com', password='pw')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.category = Category.objects.create(name='Phones')
        self.product1 = Product.objects.create(
            name='iPhone 15', description='A phone', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category,
        )
        self.product2 = Product.objects.create(
            name='Case', description='A phone case', price=Decimal('20000.00'),
            stock_quantity=10, category=self.category,
        )
        self.client.post('/api/v1/cart-items/', {'product': self.product1.id, 'quantity': 1}, format='json')
        self.client.post('/api/v1/cart-items/', {'product': self.product2.id, 'quantity': 2}, format='json')

    def test_cart_total_price_is_sum_of_items(self):
        cart = Cart.objects.get(user=self.user)
        resp = self.client.get(f'/api/v1/cart/{cart.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        expected = Decimal('1200000.00') + (Decimal('20000.00') * 2)
        self.assertEqual(Decimal(resp.data['total_price']), expected)

    def test_clear_cart_removes_all_items_but_keeps_cart(self):
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 2)

        resp = self.client.delete('/api/v1/cart/clear/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

        cart.refresh_from_db()
        self.assertEqual(cart.items.count(), 0)
        self.assertTrue(Cart.objects.filter(id=cart.id).exists())

    def test_clear_cart_when_no_cart_exists_returns_404(self):
        other_user = User.objects.create_user(username='buyer4', email='buyer4@test.com', password='pw')
        other_client = APIClient()
        other_client.force_authenticate(other_user)

        resp = other_client.delete('/api/v1/cart/clear/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_creating_cart_directly_is_not_allowed(self):
        resp = self.client.post('/api/v1/cart/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)