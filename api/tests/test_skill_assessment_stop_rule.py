"""When the Skill Assessment stops asking: Recommendation Stability.

The assessment ends once no further single answer could change the next
topics -- never before twelve answered items, never past twenty. Reaching the
ceiling without the suggestions settling completes the assessment and reports
that the result is less certain (ADR-0003).

Stability is a function of the answers alone (ADR-0005): the next-question
endpoint decides it from the answers the client hands in, saved or not, and
the save endpoint applies the same rule to the answers it is asked to
complete with.
"""

from django.urls import reverse
from rest_framework import status

from assessments.models import AssessableTopicSet
from assessments.services.topic_skill_assessment_service import sync_topic_skill_assessment_catalog

from .base import AssessmentFlowTestCase


SET_COUNT = 22


class StopRuleFlowTestCase(AssessmentFlowTestCase):
    """A role with a 22-set catalog: enough to test floor 12 and ceiling 20.

    The sets stand in no edge, so every one sits at prerequisite depth zero
    and roadmap order alone decides the suggestion order.
    """

    role = None

    def setUp(self):
        super().setUp()
        self.role = self.qa_role
        for index in range(1, SET_COUNT + 1):
            AssessableTopicSet.objects.create(
                set_key=f'{self.role.slug}--set-{index:02d}',
                key=f'set-{index:02d}',
                role=self.role,
                title=f'Set {index:02d}',
                title_th=f'Set {index:02d}',
                node_slugs=[],
                display_order=index,
            )
        sync_topic_skill_assessment_catalog()

    def key(self, index: int) -> str:
        return f'{self.role.slug}--set-{index:02d}'

    def create_session(self):
        response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.role.slug}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()['id']

    def save(self, session_id, answers: dict, *, completed=False):
        return self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'answers': answers, 'completed': completed},
            format='json',
        )

    def next_question(self, session_id, answers: dict):
        response = self.client.post(
            reverse('assessment-session-skill-assessment-next-question', kwargs={'pk': session_id}),
            {'answers': answers},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def answers_for(self, indexes, *, value=1) -> dict:
        """Low ratings, unless told otherwise, for the given set indexes."""
        return {self.key(index): value for index in indexes}

    def answer_first_n(self, count: int, *, reverse_order=False) -> dict:
        indexes = range(SET_COUNT, SET_COUNT - count, -1) if reverse_order else range(1, count + 1)
        return self.answers_for(indexes)


class StopRuleTests(StopRuleFlowTestCase):
    def test_the_assessment_does_not_end_before_twelve_answers_even_when_settled(self):
        session_id = self.create_session()
        # Uniform low ratings in roadmap order: the first five sets are the
        # suggestions and nothing unanswered could displace them, but the
        # floor of twelve keeps the assessment asking.
        answers = self.answer_first_n(11)

        payload = self.next_question(session_id, answers)
        self.assertIsNotNone(payload['next_question'])
        self.assertFalse(payload['progress']['settled'])

        response = self.save(session_id, answers, completed=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_the_assessment_ends_once_no_further_answer_could_change_the_next_topics(self):
        session_id = self.create_session()
        answers = self.answer_first_n(12)

        payload = self.next_question(session_id, answers)
        self.assertIsNone(payload['next_question'])
        self.assertTrue(payload['progress']['settled'])

        response = self.save(session_id, answers, completed=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        state = response.json()
        self.assertTrue(state['completed'])
        self.assertEqual(state['confidence'], 'high')
        self.assertEqual(state['progress']['answered'], 12)
        self.assertEqual(state['progress']['remaining'], SET_COUNT - 12)

    def test_stability_is_decided_from_the_answers_handed_in_not_from_saves(self):
        # The client asks for the next question with answers it has not
        # saved; the verdict is the same one it will get when it saves them.
        session_id = self.create_session()
        answers = self.answer_first_n(12)

        payload = self.next_question(session_id, answers)
        self.assertIsNone(payload['next_question'])
        self.assertTrue(payload['progress']['settled'])

        unsaved_state = self.client.get(reverse('assessment-session-skill-assessment', kwargs={'pk': session_id})).json()
        self.assertEqual(unsaved_state['progress']['answered'], 0)
        self.assertFalse(unsaved_state['progress']['settled'])

        response = self.save(session_id, answers, completed=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['confidence'], 'high')

    def test_not_settled_while_a_further_answer_could_enter_the_next_topics(self):
        session_id = self.create_session()
        # Twelve low ratings that skip sets 5 and 6: the suggestions are sets
        # 1-4 and 7, and rating set 5 low would put it ahead of set 7.
        answers = self.answers_for([1, 2, 3, 4, *range(7, 15)])

        payload = self.next_question(session_id, answers)
        self.assertFalse(payload['progress']['settled'])
        self.assertEqual(payload['next_question']['id'], self.key(5))

        # With set 5 answered, set 6 could only ever be sixth: settled.
        payload = self.next_question(session_id, {**answers, self.key(5): 1})
        self.assertTrue(payload['progress']['settled'])
        self.assertIsNone(payload['next_question'])

    def test_the_assessment_never_asks_more_than_twenty_items(self):
        session_id = self.create_session()
        # Answering from the back of the catalog leaves the first sets
        # unanswered, and any of them rated low would lead the suggestions, so
        # nothing settles -- the ceiling is what stops the asking.
        answers = self.answer_first_n(20, reverse_order=True)

        payload = self.next_question(session_id, answers)
        self.assertIsNone(payload['next_question'])
        self.assertFalse(payload['progress']['settled'])

    def test_reaching_the_ceiling_without_stability_completes_with_low_confidence(self):
        session_id = self.create_session()
        answers = self.answer_first_n(20, reverse_order=True)

        response = self.save(session_id, answers, completed=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        state = response.json()
        self.assertTrue(state['completed'])
        self.assertEqual(state['confidence'], 'low')

    def test_a_refused_completion_leaves_the_saved_answers_intact(self):
        # The completion decision and the answer save are one transaction: a
        # refused completion rolls back its own answers rather than leaving
        # them recorded.
        session_id = self.create_session()
        answers = self.answer_first_n(12)
        self.assertEqual(self.save(session_id, answers).status_code, status.HTTP_200_OK)

        # Twelve unsettled answers from the back of the catalog: completion is
        # refused, and nothing from that request survives.
        unsettled = self.answer_first_n(12, reverse_order=True)
        response = self.save(session_id, unsettled, completed=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        state = self.client.get(reverse('assessment-session-skill-assessment', kwargs={'pk': session_id})).json()
        self.assertEqual(state['answers'], answers)
        self.assertEqual(state['progress']['answered'], 12)
        self.assertFalse(state['completed'])

    def test_question_selection_is_deterministic(self):
        session_id = self.create_session()
        answers = {self.key(1): 1, self.key(3): 4}

        first = self.next_question(session_id, answers)
        second = self.next_question(session_id, answers)

        self.assertEqual(first['next_question'], second['next_question'])

    def test_the_respondent_sees_how_many_questions_remain(self):
        session_id = self.create_session()
        answers = self.answer_first_n(3)
        self.assertEqual(self.save(session_id, answers).status_code, status.HTTP_200_OK)

        payload = self.next_question(session_id, answers)
        self.assertEqual(payload['progress']['answered'], 3)
        self.assertEqual(payload['progress']['total'], SET_COUNT)
        self.assertEqual(payload['progress']['remaining'], SET_COUNT - 3)

        state_response = self.client.get(reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}))
        self.assertEqual(state_response.json()['progress']['remaining'], SET_COUNT - 3)

    def test_an_earlier_answer_can_be_revised(self):
        session_id = self.create_session()
        answers = self.answer_first_n(4)
        self.save(session_id, answers)

        revised = {**answers, self.key(2): 5}
        response = self.save(session_id, revised)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['answers'][self.key(2)], 5)

        state = self.client.get(reverse('assessment-session-skill-assessment', kwargs={'pk': session_id})).json()
        revised_states = {item['topic_slug']: item for item in state['topic_states']}
        self.assertEqual(revised_states[self.key(2)]['state'], 'held')
        self.assertNotIn(self.key(2), [item['topic_slug'] for item in state['recommended_topics']])

    def test_a_fully_answered_small_catalog_is_settled(self):
        # Nothing is left to ask, so no further answer could change anything.
        AssessableTopicSet.objects.filter(role=self.role, display_order__gt=8).delete()
        sync_topic_skill_assessment_catalog()
        session_id = self.create_session()
        answers = self.answer_first_n(8)

        payload = self.next_question(session_id, answers)
        self.assertIsNone(payload['next_question'])
        self.assertTrue(payload['progress']['settled'])
        self.assertEqual(payload['progress'], {'answered': 8, 'total': 8, 'remaining': 0, 'floor': 8, 'ceiling': 8, 'settled': True})

        response = self.save(session_id, answers, completed=True)
        self.assertEqual(response.json()['confidence'], 'high')
