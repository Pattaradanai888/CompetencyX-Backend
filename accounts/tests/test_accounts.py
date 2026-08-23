import uuid

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase


class AccountRegistrationTests(APITestCase):
    url = None

    def setUp(self):
        self.url = reverse('account-register')

    def test_register_creates_an_account_and_returns_a_credential(self):
        response = self.client.post(
            self.url,
            {'email': 'respondent@example.com', 'password': 'roadmap-topic-99'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertEqual(payload['user']['email'], 'respondent@example.com')
        self.assertTrue(payload['token'])
        user = get_user_model().objects.get(email='respondent@example.com')
        self.assertEqual(Token.objects.get(user=user).key, payload['token'])

    def test_register_normalizes_the_email_case(self):
        response = self.client.post(
            self.url,
            {'email': 'Respondent@Example.com', 'password': 'roadmap-topic-99'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()['user']['email'], 'respondent@example.com')

    def test_register_rejects_a_duplicate_email(self):
        self.client.post(self.url, {'email': 'taken@example.com', 'password': 'roadmap-topic-99'}, format='json')

        response = self.client.post(
            self.url,
            {'email': 'TAKEN@example.com', 'password': 'roadmap-topic-77'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['email'], ['An account with this email already exists.'])
        self.assertEqual(get_user_model().objects.filter(email='taken@example.com').count(), 1)

    def test_register_rejects_an_email_too_long_to_store(self):
        long_email = f'{"a" * 200}@example.com'

        response = self.client.post(self.url, {'email': long_email, 'password': 'roadmap-topic-99'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.json())
        self.assertFalse(get_user_model().objects.filter(email=long_email).exists())

    def test_register_rejects_a_password_that_fails_validation(self):
        response = self.client.post(self.url, {'email': 'weak@example.com', 'password': '123'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.json())
        self.assertFalse(get_user_model().objects.filter(email='weak@example.com').exists())


class AccountSignInTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('account-register')
        self.sign_in_url = reverse('account-sign-in')
        self.client.post(
            self.register_url,
            {'email': 'respondent@example.com', 'password': 'roadmap-topic-99'},
            format='json',
        )

    def test_sign_in_returns_a_credential(self):
        response = self.client.post(
            self.sign_in_url,
            {'email': 'respondent@example.com', 'password': 'roadmap-topic-99'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertTrue(payload['token'])
        self.assertEqual(payload['user']['email'], 'respondent@example.com')

    def test_sign_in_accepts_a_differently_cased_email(self):
        response = self.client.post(
            self.sign_in_url,
            {'email': 'Respondent@Example.COM', 'password': 'roadmap-topic-99'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sign_in_with_the_wrong_password_is_refused(self):
        response = self.client.post(
            self.sign_in_url,
            {'email': 'respondent@example.com', 'password': 'not-the-password'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['detail'], ['Email or password is incorrect.'])

    def test_sign_in_for_an_unknown_email_is_refused_the_same_way(self):
        response = self.client.post(
            self.sign_in_url,
            {'email': 'stranger@example.com', 'password': 'roadmap-topic-99'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['detail'], ['Email or password is incorrect.'])


class CurrentAccountTests(APITestCase):
    def setUp(self):
        self.me_url = reverse('account-me')
        self.sign_out_url = reverse('account-sign-out')
        response = self.client.post(
            reverse('account-register'),
            {'email': 'respondent@example.com', 'password': 'roadmap-topic-99'},
            format='json',
        )
        self.token = response.json()['token']

    def _authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token}')

    def test_an_account_is_identified_by_a_uuid(self):
        self._authenticate()

        identity = self.client.get(self.me_url).json()

        self.assertEqual(uuid.UUID(identity['id']), get_user_model().objects.get(email='respondent@example.com').id)

    def test_a_signed_in_respondent_receives_their_own_identity(self):
        self._authenticate()

        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['email'], 'respondent@example.com')

    def test_who_am_i_is_refused_when_signed_out(self):
        response = self.client.get(self.me_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_sign_out_invalidates_the_credential(self):
        self._authenticate()

        sign_out = self.client.post(self.sign_out_url)

        self.assertEqual(sign_out.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.client.get(self.me_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Token.objects.filter(key=self.token).exists())

    def test_sign_out_requires_a_credential(self):
        response = self.client.post(self.sign_out_url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UnauthenticatedEndpointsTests(APITestCase):
    def test_health_check_keeps_working_without_an_account(self):
        response = self.client.get(reverse('health-check'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_the_catalog_keeps_working_without_an_account(self):
        response = self.client.get(reverse('role-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_session_can_still_be_created_without_an_account(self):
        response = self.client.post(reverse('assessment-session-list'), {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
