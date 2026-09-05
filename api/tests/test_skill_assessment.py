"""The Skill Assessment endpoints: state, catalog, and next question.

Every item is one of the target role's Assessable Topic Sets (ADR-0002,
ADR-0003). There is no role-independent fallback: a session whose role has no
authored sets is served an empty catalog rather than items about nothing in
particular (ADR-0005).
"""

from django.urls import reverse
from rest_framework import status

from assessments.models import SkillAssessmentDimension, SkillAssessmentQuestion, SkillAssessmentRoleGuidance
from assessments.services.skill_assessment_service import CATALOG_VERSION

from .test_topic_states_and_ordering import TopicSetFlowTestCase


class SkillAssessmentTests(TopicSetFlowTestCase):
    """The backend role carries five authored sets (see the base class)."""

    SET_COUNT = 5

    def state_url(self, session_id):
        return reverse('assessment-session-skill-assessment', kwargs={'pk': session_id})

    def catalog_url(self, session_id):
        return reverse('assessment-session-skill-assessment-catalog', kwargs={'pk': session_id})

    def next_url(self, session_id):
        return reverse('assessment-session-skill-assessment-next-question', kwargs={'pk': session_id})

    def test_skill_assessment_state_can_be_saved_and_loaded_per_session(self):
        session_id = self.create_session()

        initial_state_response = self.client.get(self.state_url(session_id))
        self.assertEqual(initial_state_response.status_code, status.HTTP_200_OK)
        initial = initial_state_response.json()
        self.assertEqual(initial['completed'], False)
        self.assertEqual(initial['answers'], {})
        self.assertIsNone(initial['completed_at'])
        self.assertEqual(initial['topic_mastery'], {})
        self.assertEqual(len(initial['topic_states']), self.SET_COUNT)
        self.assertEqual(
            initial['progress'],
            {
                'answered': 0,
                'total': self.SET_COUNT,
                'remaining': self.SET_COUNT,
                'floor': self.SET_COUNT,
                'ceiling': self.SET_COUNT,
                'settled': False,
            },
        )
        self.assertIsNone(initial['confidence'])

        # A five-set catalog has a ceiling of five, so answering every set
        # is what lets completion through the stop rule.
        answers = {
            'backend-developer--internet-and-web': 4,
            'backend-developer--data-storage': 4,
            'backend-developer--caching': 3,
            'backend-developer--api-design': 5,
            'backend-developer--testing': 3,
        }
        payload = {'completed': True, 'answers': answers, 'completed_at': '2000-01-01T00:00:00Z'}
        save_response = self.client.post(self.state_url(session_id), payload, format='json')
        self.assertEqual(save_response.status_code, status.HTTP_200_OK)
        self.assertEqual(save_response.json()['completed'], True)
        # completed_at is set by the server, never taken from the client.
        self.assertNotEqual(save_response.json()['completed_at'], payload['completed_at'])
        self.assertEqual(save_response.json()['answers']['backend-developer--api-design'], 5)

        loaded_response = self.client.get(self.state_url(session_id))
        self.assertEqual(loaded_response.status_code, status.HTTP_200_OK)
        self.assertEqual(loaded_response.json()['completed'], True)
        self.assertEqual(loaded_response.json()['answers'], answers)
        self.assertIsNotNone(loaded_response.json()['completed_at'])

        reopened_response = self.client.post(
            self.state_url(session_id),
            {'completed': False, 'answers': answers, 'completed_at': '2000-01-01T00:00:00Z'},
            format='json',
        )
        self.assertEqual(reopened_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(reopened_response.json()['completed_at'])

    def test_skill_assessment_state_rejects_invalid_answer_scale(self):
        session_id = self.create_session()

        save_response = self.client.post(self.state_url(session_id), {'answers': {'backend-developer--caching': 7}}, format='json')

        self.assertEqual(save_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('answers', save_response.json())

    def test_skill_assessment_state_rejects_an_answer_to_another_role_s_item(self):
        session_id = self.create_session()

        save_response = self.client.post(self.state_url(session_id), {'answers': {'qa-engineer--test-design': 3}}, format='json')

        self.assertEqual(save_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('answers', save_response.json())

    def test_skill_assessment_catalog_returns_the_target_role_s_items(self):
        session_id = self.create_session()

        response = self.client.get(self.catalog_url(session_id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload['version'], CATALOG_VERSION)
        self.assertEqual(len(payload['questions']), self.SET_COUNT)
        self.assertEqual(
            [question['id'] for question in payload['questions']],
            [
                'backend-developer--internet-and-web',
                'backend-developer--data-storage',
                'backend-developer--caching',
                'backend-developer--api-design',
                'backend-developer--testing',
            ],
        )
        self.assertEqual({dimension['key'] for dimension in payload['dimensions']}, {question['id'] for question in payload['questions']})
        for dimension in payload['dimensions']:
            self.assertNotIn('track', dimension)
        self.assertTrue(any('API contracts' in guidance for guidance in payload['role_guidance']))

    def test_skill_assessment_catalog_is_empty_for_a_role_with_no_authored_sets(self):
        # The QA role has no sets in this fixture. Nothing is read off its
        # roadmap and nothing stands in for the missing sets (ADR-0005).
        response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.qa_role.slug}, format='json')
        session_id = response.json()['id']

        payload = self.client.get(self.catalog_url(session_id)).json()

        self.assertEqual(payload['questions'], [])
        self.assertEqual(payload['dimensions'], [])
        self.assertTrue(payload['role_guidance'])
        state = self.client.get(self.state_url(session_id)).json()
        self.assertEqual(state['topic_states'], [])
        self.assertEqual(state['progress']['total'], 0)

    def test_skill_assessment_catalog_questions_are_loaded_from_database(self):
        session_id = self.create_session()

        skill_assessment_question = SkillAssessmentQuestion.objects.get(question_id='backend-developer--internet-and-web')
        skill_assessment_question.prompt = 'Database-backed Skill Assessment prompt'
        skill_assessment_question.save(update_fields=['prompt', 'updated_at'])

        payload = self.client.get(self.catalog_url(session_id)).json()
        self.assertEqual(payload['questions'][0]['id'], 'backend-developer--internet-and-web')
        self.assertEqual(payload['questions'][0]['prompt'], 'Database-backed Skill Assessment prompt')

    def test_skill_assessment_catalog_dimensions_and_role_guidance_are_loaded_from_database(self):
        session_id = self.create_session()

        dimension = SkillAssessmentDimension.objects.get(dimension_key='backend-developer--internet-and-web')
        dimension.label = 'Database-backed label'
        dimension.low_score_action = 'Database-backed action'
        dimension.save(update_fields=['label', 'low_score_action', 'updated_at'])

        guidance = SkillAssessmentRoleGuidance.objects.filter(role=self.backend_role, display_order=1).first()
        guidance.guidance = 'Database-backed backend guidance'
        guidance.save(update_fields=['guidance', 'updated_at'])

        payload = self.client.get(self.catalog_url(session_id)).json()
        self.assertEqual(payload['dimensions'][0]['key'], 'backend-developer--internet-and-web')
        self.assertEqual(payload['dimensions'][0]['label'], 'Database-backed label')
        self.assertEqual(payload['dimensions'][0]['low_score_action'], 'Database-backed action')
        self.assertEqual(payload['role_guidance'][0], 'Database-backed backend guidance')

    def test_completed_skill_assessment_refuses_to_stop_before_the_floor(self):
        # The stop rule owns completion: for a five-set catalog the floor is
        # five, so one answer cannot complete the assessment even though
        # every remaining key is known.
        session_id = self.create_session()

        save_response = self.client.post(
            self.state_url(session_id),
            {'completed': True, 'answers': {'backend-developer--caching': 4}},
            format='json',
        )

        self.assertEqual(save_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('completed', save_response.json())

    def test_skill_assessment_next_question_returns_an_unanswered_item(self):
        session_id = self.create_session()

        response = self.client.post(self.next_url(session_id), {'answers': {'backend-developer--internet-and-web': 4}}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertIsNotNone(payload['next_question'])
        self.assertNotEqual(payload['next_question']['id'], 'backend-developer--internet-and-web')
        self.assertEqual(payload['progress']['answered'], 1)

    def test_next_question_selection_is_deterministic_and_asks_the_current_suggestions_first(self):
        # Selection used to be epsilon-greedy over a learned Q-table whose
        # reward was agreement, so it learned to ask the items a respondent
        # already agrees with. ADR-0003 replaced it: the same answers produce
        # the same next question, and the item asked is the one whose rating
        # would move the suggestions most -- the first current suggestion.
        session_id = self.create_session()

        first = self.client.post(self.next_url(session_id), {'answers': {}}, format='json').json()
        second = self.client.post(self.next_url(session_id), {'answers': {}}, format='json').json()
        self.assertEqual(first['next_question'], second['next_question'])
        self.assertEqual(first['next_question']['id'], 'backend-developer--internet-and-web')

        # Holding the first set moves the suggestions on: caching (no
        # prerequisites) is now the first suggestion, and is asked next.
        after_first = self.client.post(self.next_url(session_id), {'answers': {'backend-developer--internet-and-web': 5}}, format='json').json()
        self.assertEqual(after_first['next_question']['id'], 'backend-developer--caching')

    def test_next_question_is_null_when_every_item_is_answered(self):
        session_id = self.create_session()

        question_ids = SkillAssessmentQuestion.objects.filter(is_active=True, role=self.backend_role).values_list('question_id', flat=True)
        everything = dict.fromkeys(question_ids, 3)
        response = self.client.post(self.next_url(session_id), {'answers': everything}, format='json').json()

        self.assertIsNone(response['next_question'])
        self.assertEqual(response['progress']['remaining'], 0)

    def test_next_question_rejects_an_unknown_answer_key(self):
        session_id = self.create_session()

        response = self.client.post(self.next_url(session_id), {'answers': {'backend-developer--no-such-set': 3}}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('answers', response.json())

    def test_skill_assessment_state_survives_removing_and_readding_an_answer(self):
        session_id = self.create_session()
        url = self.state_url(session_id)

        self.client.post(url, {'answers': {'backend-developer--caching': 5}}, format='json')
        cleared_response = self.client.post(url, {'answers': {}}, format='json')
        self.assertEqual(cleared_response.json()['answers'], {})

        response = self.client.post(url, {'answers': {'backend-developer--caching': 5}}, format='json')
        self.assertEqual(response.json()['answers'], {'backend-developer--caching': 5})

        # No per-answer learning bookkeeping leaks into the session (ADR-0003).
        session_response = self.client.get(reverse('assessment-session-detail', kwargs={'pk': session_id}))
        self.assertNotIn('_skill_assessment_feedback_applied_question_ids', session_response.json()['profile'])
