"""Marking an Assessable Topic Set as something the respondent can already do.

A mark is the respondent's own statement, it belongs to the account rather
than the session, and it has exactly the effect a top self-rating has: the
set becomes a Held Topic and stops being suggested (ADR-0003).
"""

from django.urls import reverse
from rest_framework import status

from .test_topic_states_and_ordering import TopicSetFlowTestCase


MARK_URL_NAME = 'assessment-session-skill-assessment-held-topics'
UNMARK_URL_NAME = 'assessment-session-skill-assessment-unhold-topic'


class HeldTopicMarkTests(TopicSetFlowTestCase):
    def setUp(self):
        super().setUp()
        self.token = self.register('respondent@example.com', 'a-long-enough-passphrase')

    def register(self, email, password='a-long-enough-passphrase'):
        response = self.client.post(
            reverse('account-register'),
            {'email': email, 'password': password},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()['token']

    def create_owned_session(self):
        response = self.client.post(
            reverse('assessment-session-list'),
            {'preferred_role_slug': self.backend_role.slug},
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.token}',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()['id']

    def mark(self, session_id, topic_key):
        return self.client.post(
            reverse(MARK_URL_NAME, kwargs={'pk': session_id}),
            {'topic_key': topic_key},
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.token}',
        )

    def unmark(self, session_id, topic_key):
        return self.client.delete(
            reverse(UNMARK_URL_NAME, kwargs={'pk': session_id, 'topic_key': topic_key}),
            HTTP_AUTHORIZATION=f'Token {self.token}',
        )

    def suggested_slugs(self, session_id):
        state = self.client.get(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            HTTP_AUTHORIZATION=f'Token {self.token}',
        ).json()
        return [item['topic_slug'] for item in state['recommended_topics']]

    def test_a_signed_in_respondent_can_mark_and_unmark_a_set(self):
        session_id = self.create_owned_session()

        mark_response = self.mark(session_id, 'backend-developer--caching')
        self.assertEqual(mark_response.status_code, status.HTTP_200_OK)

        state = mark_response.json()
        marked = next(item for item in state['topic_states'] if item['topic_slug'] == 'backend-developer--caching')
        self.assertEqual(marked['state'], 'held')
        self.assertIn('You said', marked['statement'])

        unmark_response = self.unmark(session_id, 'backend-developer--caching')
        self.assertEqual(unmark_response.status_code, status.HTTP_200_OK)
        restored = next(
            item for item in unmark_response.json()['topic_states'] if item['topic_slug'] == 'backend-developer--caching'
        )
        self.assertEqual(restored['state'], 'unassessed')

    def test_a_marked_set_stops_appearing_among_the_suggestions_immediately(self):
        session_id = self.create_owned_session()
        self.save_answers(session_id, by_set_key={'data-storage': 1})

        before = self.suggested_slugs(session_id)
        self.assertIn('backend-developer--caching', before)

        self.mark(session_id, 'backend-developer--caching')

        after = self.suggested_slugs(session_id)
        self.assertNotIn('backend-developer--caching', after)

    def test_a_mark_and_a_top_self_rating_have_the_same_effect(self):
        rated = self.create_owned_session()
        marked = self.create_owned_session()
        self.save_answers(rated, by_set_key={'caching': 5})
        self.mark(marked, 'backend-developer--caching')

        def held_state(session_id):
            state = self.client.get(
                reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
                HTTP_AUTHORIZATION=f'Token {self.token}',
            ).json()
            return next(item for item in state['topic_states'] if item['topic_slug'] == 'backend-developer--caching')['state']

        self.assertEqual(held_state(rated), 'held')
        self.assertEqual(held_state(marked), 'held')
        self.assertNotIn('backend-developer--caching', self.suggested_slugs(rated))
        self.assertNotIn('backend-developer--caching', self.suggested_slugs(marked))

    def test_a_mark_persists_into_a_new_session_for_the_same_account(self):
        first = self.create_owned_session()
        self.mark(first, 'backend-developer--caching')

        second = self.create_owned_session()
        state = self.client.get(
            reverse('assessment-session-skill-assessment', kwargs={'pk': second}),
            HTTP_AUTHORIZATION=f'Token {self.token}',
        ).json()

        marked = next(item for item in state['topic_states'] if item['topic_slug'] == 'backend-developer--caching')
        self.assertEqual(marked['state'], 'held')
        self.assertNotIn('backend-developer--caching', [item['topic_slug'] for item in state['recommended_topics']])

    def test_a_mark_by_one_account_has_no_effect_on_another(self):
        marker_session = self.create_owned_session()
        self.mark(marker_session, 'backend-developer--caching')

        other_token = self.register('other@example.com')
        response = self.client.post(
            reverse('assessment-session-list'),
            {'preferred_role_slug': self.backend_role.slug},
            format='json',
            HTTP_AUTHORIZATION=f'Token {other_token}',
        )
        other_session = response.json()['id']
        state = self.client.get(
            reverse('assessment-session-skill-assessment', kwargs={'pk': other_session}),
            HTTP_AUTHORIZATION=f'Token {other_token}',
        ).json()

        caching = next(item for item in state['topic_states'] if item['topic_slug'] == 'backend-developer--caching')
        self.assertEqual(caching['state'], 'unassessed')
        self.assertIn('backend-developer--caching', [item['topic_slug'] for item in state['recommended_topics']])

    def test_an_unauthenticated_mark_is_refused_with_a_plain_message(self):
        response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        session_id = response.json()['id']

        mark_response = self.client.post(
            reverse(MARK_URL_NAME, kwargs={'pk': session_id}),
            {'topic_key': 'backend-developer--caching'},
            format='json',
        )

        self.assertEqual(mark_response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('requires an account', str(mark_response.json()['detail']))

    def test_marking_an_unknown_set_is_reported(self):
        session_id = self.create_owned_session()

        mark_response = self.mark(session_id, 'backend-developer--no-such-set')

        self.assertEqual(mark_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('topic_key', mark_response.json())

    def test_only_a_held_topic_that_was_marked_offers_the_undo(self):
        """A mark can be taken back; a top self-rating has no mark to take back.

        The page shows the undo control only where it does something, so each
        held entry says which kind of statement holds it.
        """
        session_id = self.create_owned_session()
        self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'answers': {'backend-developer--internet-and-web': 5}, 'completed': False},
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.token}',
        )
        self.mark(session_id, 'backend-developer--caching')

        state = self.client.get(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            HTTP_AUTHORIZATION=f'Token {self.token}',
        ).json()
        by_slug = {item['topic_slug']: item for item in state['topic_states']}

        self.assertTrue(by_slug['backend-developer--caching']['held_by_mark'])
        self.assertFalse(by_slug['backend-developer--internet-and-web']['held_by_mark'])
        # A unit that is not held has no mark to speak of, so it carries no flag.
        self.assertNotIn('held_by_mark', by_slug['backend-developer--data-storage'])

    def test_a_set_held_by_a_top_rating_offers_no_undo_even_when_also_marked(self):
        """Taking the mark back would leave the set held, so the control would do nothing."""
        session_id = self.create_owned_session()
        self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'answers': {'backend-developer--caching': 5}, 'completed': False},
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.token}',
        )
        state = self.mark(session_id, 'backend-developer--caching').json()

        caching = next(item for item in state['topic_states'] if item['topic_slug'] == 'backend-developer--caching')
        self.assertEqual(caching['state'], 'held')
        self.assertFalse(caching['held_by_mark'])
