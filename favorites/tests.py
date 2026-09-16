from django.test import TestCase
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from products.models import Product, Category
from .models import Favorite

User = get_user_model()


class FavoriteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='buyer', email='buyer@test.com', password='pw')
        self.other_user = User.objects.create_user(username='other', email='other@test.com', password='pw')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.category = Category.objects.create(name='Phones')
        self.product = Product.objects.create(
            name='iPhone 15', price=Decimal('1200000.00'),
            stock_quantity=5, category=self.category,
        )

    def test_add_favorite(self):
        resp = self.client.post('/api/v1/favorites/', {'product': self.product.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(Favorite.objects.filter(user=self.user, product=self.product).exists())

    def test_cannot_favorite_same_product_twice(self):
        self.client.post('/api/v1/favorites/', {'product': self.product.id}, format='json')
        resp = self.client.post('/api/v1/favorites/', {'product': self.product.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_toggle_adds_then_removes(self):
        resp1 = self.client.post('/api/v1/favorites/toggle/', {'product': self.product.id}, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)
        self.assertTrue(resp1.data['favorited'])

        resp2 = self.client.post('/api/v1/favorites/toggle/', {'product': self.product.id}, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertFalse(resp2.data['favorited'])

        self.assertFalse(Favorite.objects.filter(user=self.user, product=self.product).exists())

    def test_list_only_shows_own_favorites(self):
        Favorite.objects.create(user=self.other_user, product=self.product)
        resp = self.client.get('/api/v1/favorites/')
        self.assertEqual(len(resp.data['results']), 0)

    def test_delete_favorite(self):
        fav = Favorite.objects.create(user=self.user, product=self.product)
        resp = self.client.delete(f'/api/v1/favorites/{fav.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Favorite.objects.filter(id=fav.id).exists())

    def test_cannot_delete_another_users_favorite(self):
        fav = Favorite.objects.create(user=self.other_user, product=self.product)
        resp = self.client.delete(f'/api/v1/favorites/{fav.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

# Create your tests here.
