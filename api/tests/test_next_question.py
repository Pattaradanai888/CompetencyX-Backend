"""Role Discovery serves "the next question" through its own read-only endpoint.

Ticket 004: Skill Assessment already has an explicit next-question endpoint, so
Role Discovery burying ``current_question`` inside the session payload made the
two surveys different shapes for the same idea. Selection is a pure function --
the first eligible unanswered question by ``display_order`` -- so the endpoint is
a safe GET, and these tests hold that it stays one.
"""

import json

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework import status

from assessments.models import AssessmentSession

from .base import AssessmentFlowTestCase


WRITE_STATEMENTS = ('INSERT', 'UPDATE', 'DELETE')


class RoleDiscoveryNextQuestionTests(AssessmentFlowTestCase):
    def _create_session(self, **payload):
        response = self.client.post(reverse('assessment-session-list'), payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()

    def _next_question_url(self, session_id):
        return reverse('assessment-session-next-question', kwargs={'pk': session_id})

    def test_an_in_progress_session_serves_the_same_question_the_session_payload_carries(self):
        session = self._create_session(preferred_role_slug=self.backend_role.slug)

        response = self.client.get(self._next_question_url(session['id']))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload['next_question'], session['current_question'])
        self.assertEqual(payload['next_question']['code'], 'role-core-01')
        self.assertEqual([choice['value'] for choice in payload['next_question']['response_scale']], [2, 1, 0, -1, -2])

    def test_the_question_follows_the_session_language(self):
        session = self._create_session(language=AssessmentSession.Language.TH)

        payload = self.client.get(self._next_question_url(session['id'])).json()

        self.assertEqual(payload['next_question']['prompt'], 'คำถามบทบาท 1')

    def test_the_question_advances_as_answers_are_submitted(self):
        session = self._create_session()
        first = self.client.get(self._next_question_url(session['id'])).json()['next_question']

        self.client.post(
            reverse('assessment-session-answers', kwargs={'pk': session['id']}),
            {'question_id': first['id'], 'scale_value': 2},
            format='json',
        )

        second = self.client.get(self._next_question_url(session['id'])).json()['next_question']
        self.assertNotEqual(second['id'], first['id'])
        self.assertEqual(second['code'], 'role-core-02')

    def test_an_exhausted_role_stage_serves_a_null_question(self):
        session = self._create_session()
        final_payload = self._answer_remaining_core_questions(session['id'], session)
        self.assertIsNone(final_payload['current_question'])

        response = self.client.get(self._next_question_url(session['id']))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()['next_question'])

    def test_a_completed_session_serves_a_null_question_even_with_questions_left(self):
        session = self._create_session()
        AssessmentSession.objects.filter(id=session['id']).update(status=AssessmentSession.Status.COMPLETED)

        response = self.client.get(self._next_question_url(session['id']))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()['next_question'])

    def test_the_endpoint_writes_nothing(self):
        session = self._create_session()
        session_row = AssessmentSession.objects.get(id=session['id'])

        with CaptureQueriesContext(connection) as queries:
            self.client.get(self._next_question_url(session['id']))

        written = [query['sql'] for query in queries if query['sql'].lstrip().upper().startswith(WRITE_STATEMENTS)]
        self.assertEqual(written, [])
        self.assertEqual(AssessmentSession.objects.get(id=session['id']).updated_at, session_row.updated_at)

    def test_an_unknown_session_is_not_found(self):
        response = self.client.get(self._next_question_url('2b39d41d-8de9-4b9b-b2ef-2a278b3f3770'))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_current_question_stays_in_the_session_payload_during_the_deprecation_window(self):
        session = self._create_session()

        detail = self.client.get(reverse('assessment-session-detail', kwargs={'pk': session['id']})).json()

        self.assertIn('current_question', detail)
        self.assertEqual(detail['current_question']['code'], 'role-core-01')

    def test_the_endpoint_is_documented_in_the_openapi_schema(self):
        schema_payload = json.loads(self.client.get(reverse('api-schema'), HTTP_ACCEPT='application/json').content)
        operation = schema_payload['paths']['/api/v1/assessment-sessions/{id}/next-question/']['get']

        self.assertEqual(operation['operationId'], 'getAssessmentNextQuestion')
        self.assertIn('404', operation['responses'])
        self.assertIn('RoleDiscoveryNextQuestionResponse', schema_payload['components']['schemas'])
