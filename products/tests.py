from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from .models import Product, Category
from favorites.models import Favorite

User = get_user_model()


class ProductCreationTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller', email='seller@test.com', password='pw')
        self.other_user = User.objects.create_user(username='other', email='other@test.com', password='pw')
        self.staff = User.objects.create_user(username='staff', email='staff@test.com', password='pw', is_staff=True)
        self.category = Category.objects.create(name='Phones')

        self.client = APIClient()
        self.client.force_authenticate(self.seller)

    def _payload(self, **overrides):
        data = {
            'name': 'iPhone 15',
            'description': 'A great phone',
            'price': '1200000.00',
            'stock_quantity': 5,
            'category': self.category.id,
        }
        data.update(overrides)
        return data

    def test_create_product_assigns_seller_from_request(self):
        resp = self.client.post('/api/v1/products/', self._payload(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        product = Product.objects.get(id=resp.data['id'])
        self.assertEqual(product.seller, self.seller)

    def test_seller_cannot_be_spoofed(self):
        resp = self.client.post(
            '/api/v1/products/', self._payload(seller=self.other_user.id), format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        product = Product.objects.get(id=resp.data['id'])
        self.assertEqual(product.seller, self.seller)  # not other_user

    def test_price_must_be_positive(self):
        resp = self.client.post('/api/v1/products/', self._payload(price='0.00'), format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_name_and_description_cannot_be_identical(self):
        resp = self.client.post(
            '/api/v1/products/',
            self._payload(name='SameText', description='SameText'),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_user_cannot_create_product(self):
        anon_client = APIClient()
        resp = anon_client.post('/api/v1/products/', self._payload(), format='json')
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class ProductReadAccessTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller', email='seller2@test.com', password='pw')
        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', description='A phone', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category, seller=self.seller,
        )
        self.client = APIClient()  # anonymous, no auth

    def test_anonymous_user_can_list_products(self):
        resp = self.client.get('/api/v1/products/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_anonymous_user_can_retrieve_product(self):
        resp = self.client.get(f'/api/v1/products/{self.product.id}/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_anonymous_user_sees_is_favorited_false(self):
        resp = self.client.get(f'/api/v1/products/{self.product.id}/')
        self.assertFalse(resp.data['is_favorited'])


class ProductOwnershipPermissionTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller', email='seller3@test.com', password='pw')
        self.other_user = User.objects.create_user(username='other2', email='other2@test.com', password='pw')
        self.staff = User.objects.create_user(username='staff2', email='staff2@test.com', password='pw', is_staff=True)
        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', description='A phone', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category, seller=self.seller,
        )

    def test_non_owner_cannot_update_product(self):
        client = APIClient()
        client.force_authenticate(self.other_user)
        resp = client.patch(f'/api/v1/products/{self.product.id}/', {'price': '999.00'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_update_own_product(self):
        client = APIClient()
        client.force_authenticate(self.seller)
        resp = client.patch(f'/api/v1/products/{self.product.id}/', {'price': '999.00'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_staff_can_update_any_product(self):
        client = APIClient()
        client.force_authenticate(self.staff)
        resp = client.patch(f'/api/v1/products/{self.product.id}/', {'price': '999.00'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_non_owner_cannot_delete_product(self):
        client = APIClient()
        client.force_authenticate(self.other_user)
        resp = client.delete(f'/api/v1/products/{self.product.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Product.objects.filter(id=self.product.id).exists())


class CategoryTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username='staff3', email='staff3@test.com', password='pw', is_staff=True)
        self.regular_user = User.objects.create_user(username='reg', email='reg@test.com', password='pw')
        self.category = Category.objects.create(name='Phones')

    def test_anonymous_can_list_categories(self):
        client = APIClient()
        resp = client.get('/api/v1/categories/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_non_staff_cannot_create_category(self):
        client = APIClient()
        client.force_authenticate(self.regular_user)
        resp = client.post('/api/v1/categories/', {'name': 'Laptops'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_can_create_category(self):
        client = APIClient()
        client.force_authenticate(self.staff)
        resp = client.post('/api/v1/categories/', {'name': 'Laptops'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_cannot_delete_category_with_products(self):
        Product.objects.create(
            name='iPhone 15', description='A phone', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category, seller=self.staff,
        )
        client = APIClient()
        client.force_authenticate(self.staff)
        resp = client.delete(f'/api/v1/categories/{self.category.id}/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Category.objects.filter(id=self.category.id).exists())

    def test_can_delete_empty_category(self):
        empty_category = Category.objects.create(name='Empty Category')
        client = APIClient()
        client.force_authenticate(self.staff)
        resp = client.delete(f'/api/v1/categories/{empty_category.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class ProductFavoriteIntegrationTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(username='seller4', email='seller4@test.com', password='pw')
        self.buyer = User.objects.create_user(username='buyer4', email='buyer4@test.com', password='pw')
        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', description='A phone', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category, seller=self.seller,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.buyer)

    def test_is_favorited_false_by_default(self):
        resp = self.client.get(f'/api/v1/products/{self.product.id}/')
        self.assertFalse(resp.data['is_favorited'])

    def test_is_favorited_true_after_favoriting(self):
        Favorite.objects.create(user=self.buyer, product=self.product)
        resp = self.client.get(f'/api/v1/products/{self.product.id}/')
        self.assertTrue(resp.data['is_favorited'])

    def test_is_favorited_does_not_leak_across_users(self):
        other_buyer = User.objects.create_user(username='buyer5', email='buyer5@test.com', password='pw')
        Favorite.objects.create(user=other_buyer, product=self.product)

        resp = self.client.get(f'/api/v1/products/{self.product.id}/')
        self.assertFalse(resp.data['is_favorited'])  # this user hasn't favorited it
