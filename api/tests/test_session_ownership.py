from django.urls import reverse
from rest_framework import status

from assessments.models import AssessmentSession

from .base import AssessmentFlowTestCase


class SessionOwnershipTests(AssessmentFlowTestCase):
    def setUp(self):
        super().setUp()
        self.owner_token = self._register('owner@example.com')
        self.other_token = self._register('other@example.com')

    def _register(self, email):
        response = self.client.post(
            reverse('account-register'),
            {'email': email, 'password': 'roadmap-topic-99'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()['token']

    def _sign_in_as(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')

    def _sign_out(self):
        self.client.credentials()

    def _create_session(self):
        response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()['id']

    def _session_scoped_urls(self, session_id):
        return [
            reverse('assessment-session-detail', kwargs={'pk': session_id}),
            reverse('assessment-session-next-question', kwargs={'pk': session_id}),
            reverse('assessment-session-results', kwargs={'pk': session_id}),
            reverse('assessment-session-insights', kwargs={'pk': session_id}),
            reverse('assessment-session-history', kwargs={'pk': session_id}),
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            reverse('assessment-session-skill-assessment-catalog', kwargs={'pk': session_id}),
        ]

    def test_a_session_created_while_signed_in_is_owned_by_that_account(self):
        self._sign_in_as(self.owner_token)

        session_id = self._create_session()

        session = AssessmentSession.objects.get(id=session_id)
        self.assertIsNotNone(session.user)
        self.assertEqual(session.user.email, 'owner@example.com')

    def test_the_owner_reads_their_own_session(self):
        self._sign_in_as(self.owner_token)
        session_id = self._create_session()

        response = self.client.get(reverse('assessment-session-detail', kwargs={'pk': session_id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['id'], session_id)

    def test_a_second_account_is_refused_on_every_session_scoped_endpoint(self):
        self._sign_in_as(self.owner_token)
        session_id = self._create_session()
        self._sign_in_as(self.other_token)

        for url in self._session_scoped_urls(session_id):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)

    def test_a_second_account_cannot_write_to_a_session_it_does_not_own(self):
        self._sign_in_as(self.owner_token)
        session_id = self._create_session()
        self._sign_in_as(self.other_token)

        answers = self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': session_id}),
            {'question_id': 1, 'scale_value': 2},
            format='json',
        )
        skill_assessment = self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'answers': {}},
            format='json',
        )
        next_question = self.client.post(
            reverse('assessment-session-skill-assessment-next-question', kwargs={'pk': session_id}),
            {'answers': {}},
            format='json',
        )

        self.assertEqual(answers.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(skill_assessment.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(next_question.status_code, status.HTTP_404_NOT_FOUND)

    def test_an_unauthenticated_reader_is_refused_an_owned_session(self):
        self._sign_in_as(self.owner_token)
        session_id = self._create_session()
        self._sign_out()

        for url in self._session_scoped_urls(session_id):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)

    def test_a_session_created_signed_out_has_no_owner_and_stays_readable(self):
        session_id = self._create_session()

        self.assertIsNone(AssessmentSession.objects.get(id=session_id).user)
        self.assertEqual(self.client.get(reverse('assessment-session-detail', kwargs={'pk': session_id})).status_code, status.HTTP_200_OK)

    def test_an_ownerless_session_is_never_assigned_to_an_account_that_reads_it(self):
        session_id = self._create_session()
        self._sign_in_as(self.owner_token)

        response = self.client.get(reverse('assessment-session-detail', kwargs={'pk': session_id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(AssessmentSession.objects.get(id=session_id).user)


class SessionListTests(AssessmentFlowTestCase):
    def setUp(self):
        super().setUp()
        response = self.client.post(
            reverse('account-register'),
            {'email': 'owner@example.com', 'password': 'roadmap-topic-99'},
            format='json',
        )
        self.owner_token = response.json()['token']

    def test_a_signed_in_respondent_lists_only_the_sessions_they_own(self):
        ownerless_session_id = self.client.post(reverse('assessment-session-list'), {}, format='json').json()['id']
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token}')
        owned_session_id = self.client.post(reverse('assessment-session-list'), {}, format='json').json()['id']

        response = self.client.get(reverse('assessment-session-list'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        listed_ids = [session['id'] for session in response.json()]
        self.assertEqual(listed_ids, [owned_session_id])
        self.assertNotIn(ownerless_session_id, listed_ids)

    def test_listing_sessions_requires_an_account(self):
        response = self.client.get(reverse('assessment-session-list'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
