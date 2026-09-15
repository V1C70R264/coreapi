from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from .models import Address

User = get_user_model()


class AddressCreationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer', email='buyer@test.com', password='pw'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _payload(self, **overrides):
        data = {
            'full_name': 'Victor Test',
            'phone_number': '+255712345678',
            'region': 'Dar es Salaam',
            'district': 'Ilala',
            'street_address': '123 Main St',
        }
        data.update(overrides)
        return data

    def test_create_address_sets_user_from_request(self):
        resp = self.client.post('/api/v1/addresses/', self._payload(), format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        address = Address.objects.get(id=resp.data['id'])
        self.assertEqual(address.user, self.user)

    def test_first_address_is_auto_default(self):
        resp = self.client.post('/api/v1/addresses/', self._payload(), format='json')
        self.assertTrue(resp.data['is_default'])

    def test_second_address_is_not_default(self):
        self.client.post('/api/v1/addresses/', self._payload(), format='json')
        resp = self.client.post(
            '/api/v1/addresses/', self._payload(street_address='456 Other St'), format='json'
        )
        self.assertFalse(resp.data['is_default'])

    def test_invalid_phone_number_rejected(self):
        resp = self.client.post(
            '/api/v1/addresses/', self._payload(phone_number='not-a-number'), format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_field_cannot_be_spoofed(self):
        other_user = User.objects.create_user(
            username='other', email='other@test.com', password='pw'
        )
        resp = self.client.post(
            '/api/v1/addresses/', self._payload(user=other_user.id), format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        address = Address.objects.get(id=resp.data['id'])
        self.assertEqual(address.user, self.user)  # not other_user

    def test_address_cap_enforced(self):
        for i in range(10):
            resp = self.client.post(
                '/api/v1/addresses/', self._payload(street_address=f'{i} St'), format='json'
            )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        resp = self.client.post(
            '/api/v1/addresses/', self._payload(street_address='11th St'), format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class AddressOwnershipTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(
            username='user_a', email='user_a@test.com', password='pw'
        )
        self.user_b = User.objects.create_user(
            username='user_b', email='user_b@test.com', password='pw'
        )
        self.address = Address.objects.create(
            user=self.user_a,
            full_name='User A',
            phone_number='+255712345678',
            region='Dar es Salaam',
            district='Ilala',
            street_address='123 Main St',
        )
        self.client_b = APIClient()
        self.client_b.force_authenticate(self.user_b)

    def test_cannot_retrieve_other_users_address(self):
        resp = self.client_b.get(f'/api/v1/addresses/{self.address.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_update_other_users_address(self):
        resp = self.client_b.patch(
            f'/api/v1/addresses/{self.address.id}/',
            {'full_name': 'Hacked'}, format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_delete_other_users_address(self):
        resp = self.client_b.delete(f'/api/v1/addresses/{self.address.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Address.objects.filter(id=self.address.id).exists())

    def test_list_only_shows_own_addresses(self):
        Address.objects.create(
            user=self.user_b,
            full_name='User B',
            phone_number='+255712345679',
            region='Dar es Salaam',
            district='Kinondoni',
            street_address='456 Other St',
        )
        resp = self.client_b.get('/api/v1/addresses/')
        ids = [item['id'] for item in resp.data['results']]
        self.assertNotIn(self.address.id, ids)


class AddressSetDefaultTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer', email='buyer@test.com', password='pw'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.addr1 = Address.objects.create(
            user=self.user, full_name='Addr 1', phone_number='+255712345678',
            region='Dar es Salaam', district='Ilala', street_address='1 St',
        )
        self.addr2 = Address.objects.create(
            user=self.user, full_name='Addr 2', phone_number='+255712345679',
            region='Dar es Salaam', district='Kinondoni', street_address='2 St',
        )

    def test_set_default_switches_default_and_unsets_previous(self):
        self.assertTrue(self.addr1.is_default)
        self.assertFalse(self.addr2.is_default)

        resp = self.client.post(f'/api/v1/addresses/{self.addr2.id}/set-default/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['is_default'])

        self.addr1.refresh_from_db()
        self.addr2.refresh_from_db()
        self.assertFalse(self.addr1.is_default)
        self.assertTrue(self.addr2.is_default)

    def test_cannot_set_default_on_another_users_address(self):
        other_user = User.objects.create_user(
            username='other', email='other@test.com', password='pw'
        )
        other_client = APIClient()
        other_client.force_authenticate(other_user)

        resp = other_client.post(f'/api/v1/addresses/{self.addr1.id}/set-default/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class AddressDeletionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer', email='buyer@test.com', password='pw'
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.addr1 = Address.objects.create(
            user=self.user, full_name='Addr 1', phone_number='+255712345678',
            region='Dar es Salaam', district='Ilala', street_address='1 St',
        )
        self.addr2 = Address.objects.create(
            user=self.user, full_name='Addr 2', phone_number='+255712345679',
            region='Dar es Salaam', district='Kinondoni', street_address='2 St',
        )

    def test_deleting_default_promotes_another(self):
        self.assertTrue(self.addr1.is_default)

        resp = self.client.delete(f'/api/v1/addresses/{self.addr1.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

        self.addr2.refresh_from_db()
        self.assertTrue(self.addr2.is_default)

# Create your tests here.
