"""The three states of an assessable unit, and the order suggestions arrive in.

A unit the assessment never asked about used to be stored as mastery 0.0 --
indistinguishable from a topic the respondent said they cannot do. After
ADR-0003 every unit is in exactly one of three states end to end: Held (the
respondent's own statement), an assessed gap, or Unassessed, and suggestions
are ordered by prerequisite layer, then roadmap order, then Self-placed
Mastery -- prerequisites always win.
"""

from django.urls import reverse
from rest_framework import status

from assessments.models import AssessableTopicSet
from assessments.services.skill_assessment_service import NEXT_TOPIC_COUNT
from assessments.services.topic_skill_assessment_service import sync_topic_skill_assessment_catalog
from roadmaps.models import ExternalRoadmapEdge, ExternalRoadmapNode

from .base import AssessmentFlowTestCase


def _node(role, external_id, slug, title, order):
    return ExternalRoadmapNode.objects.create(
        role=role,
        external_id=external_id,
        slug=slug,
        title=title,
        node_type=ExternalRoadmapNode.NodeType.TOPIC,
        display_order=order,
        source='roadmap.sh',
    )


class TopicSetFlowTestCase(AssessmentFlowTestCase):
    """A role whose Skill Assessment is built from authored Assessable Topic Sets.

    The graph below is deliberately layered against the display order, so a
    suggestion ordered by weakness alone would come out wrong:

    - internet (1) -> http (2) -> databases (3) -> apis (5)   [a prerequisite chain]
    - caching (4) and testing (6) stand in no edge at all
    """

    def setUp(self):
        super().setUp()
        self.internet = _node(self.backend_role, 'b1', 'internet', 'Internet', 1)
        self.http = _node(self.backend_role, 'b2', 'http', 'HTTP', 2)
        self.databases = _node(self.backend_role, 'b3', 'databases', 'Databases', 3)
        self.caching = _node(self.backend_role, 'b4', 'caching', 'Caching', 4)
        self.apis = _node(self.backend_role, 'b5', 'apis', 'API Design', 5)
        self.testing = _node(self.backend_role, 'b6', 'testing', 'Testing', 6)
        for source, target in (
            (self.internet, self.http),
            (self.http, self.databases),
            (self.databases, self.apis),
        ):
            ExternalRoadmapEdge.objects.create(role=self.backend_role, source_node=source, target_node=target)

        self.author_sets(
            ('internet-and-web', 'Internet and web protocols', [self.internet.slug, self.http.slug]),
            ('data-storage', 'Data storage', [self.databases.slug]),
            ('caching', 'Caching', [self.caching.slug]),
            ('api-design', 'API design', [self.apis.slug]),
            ('testing', 'Testing', [self.testing.slug]),
        )
        sync_topic_skill_assessment_catalog()

    def author_sets(self, *entries):
        for order, (key, title, node_slugs) in enumerate(entries, start=1):
            topic_set = AssessableTopicSet.objects.create(
                set_key=f'{self.backend_role.slug}--{key}',
                key=key,
                role=self.backend_role,
                title=title,
                title_th=title,
                node_slugs=list(node_slugs),
                display_order=order,
            )
            topic_set.nodes.set(ExternalRoadmapNode.objects.filter(role=self.backend_role, slug__in=node_slugs))

    def create_session(self):
        response = self.client.post(reverse('assessment-session-list'), {'preferred_role_slug': self.backend_role.slug}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()['id']

    def save_answers(self, session_id, *, by_set_key, completed=False):
        answers = {f'{self.backend_role.slug}--{key}': value for key, value in by_set_key.items()}
        return self.client.post(
            reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}),
            {'answers': answers, 'completed': completed},
            format='json',
        )

    def get_state(self, session_id):
        response = self.client.get(reverse('assessment-session-skill-assessment', kwargs={'pk': session_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()


class TopicStatesTests(TopicSetFlowTestCase):
    def _suggested_slugs(self, state):
        return [item['topic_slug'] for item in state['recommended_topics']]

    def test_all_three_states_appear_in_one_response(self):
        session_id = self.create_session()
        response = self.save_answers(session_id, by_set_key={'internet-and-web': 5, 'data-storage': 1})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        state = response.json()

        states_by_key = {item['topic_slug']: item for item in state['topic_states']}
        self.assertEqual(len(states_by_key), 5)
        self.assertEqual(states_by_key['backend-developer--internet-and-web']['state'], 'held')
        self.assertEqual(states_by_key['backend-developer--internet-and-web']['mastery'], 1.0)
        self.assertEqual(states_by_key['backend-developer--data-storage']['state'], 'assessed_gap')
        self.assertEqual(states_by_key['backend-developer--data-storage']['mastery'], 0.0)
        for key in ('caching', 'api-design', 'testing'):
            self.assertEqual(states_by_key[f'backend-developer--{key}']['state'], 'unassessed', key)
            self.assertIsNone(states_by_key[f'backend-developer--{key}']['mastery'], key)

        # A held unit drops out of the suggestions; the assessed gap comes
        # before the unassessed remainder.
        self.assertEqual(
            self._suggested_slugs(state),
            [
                'backend-developer--data-storage',
                'backend-developer--caching',
                'backend-developer--testing',
                'backend-developer--api-design',
            ],
        )
        self.assertEqual(state['recommended_topics'][0]['state'], 'assessed_gap')
        for item in state['recommended_topics'][1:]:
            self.assertEqual(item['state'], 'unassessed')

    def test_a_never_asked_set_is_never_reported_as_a_gap(self):
        session_id = self.create_session()
        state = self.get_state(session_id)

        for item in state['topic_states']:
            self.assertEqual(item['state'], 'unassessed')
            self.assertIsNone(item['mastery'])
        for item in state['recommended_topics']:
            self.assertEqual(item['state'], 'unassessed')
            self.assertNotIn(item['topic_slug'], state['topic_mastery'])

    def test_held_wording_is_the_respondents_own_statement(self):
        session_id = self.create_session()
        response = self.save_answers(session_id, by_set_key={'internet-and-web': 4})
        state = response.json()

        held = next(item for item in state['topic_states'] if item['state'] == 'held')
        self.assertIn('You said', held['statement'])
        self.assertIn('Internet and web protocols', held['statement'])
        for forbidden in ('passed', 'completed', 'verified', 'mastered', 'achieved'):
            self.assertNotIn(forbidden, held['statement'].lower())

    def test_readiness_is_computed_over_assessed_sets_only(self):
        session_id = self.create_session()
        # One answered set at the top of the scale: were the three unasked sets
        # counted as absent capability, overall mastery would be 0.2, not 1.0.
        response = self.save_answers(session_id, by_set_key={'data-storage': 5})
        state = response.json()

        self.assertEqual(state['readiness']['assessed_count'], 1)
        self.assertEqual(state['readiness']['overall_mastery'], 1.0)

    def test_readiness_grows_as_more_sets_are_assessed_without_falling(self):
        session_id = self.create_session()
        one = self.save_answers(session_id, by_set_key={'data-storage': 5}).json()
        two = self.save_answers(session_id, by_set_key={'data-storage': 5, 'caching': 5}).json()

        self.assertEqual(one['readiness']['assessed_count'], 1)
        self.assertEqual(two['readiness']['assessed_count'], 2)
        self.assertEqual(two['readiness']['overall_mastery'], 1.0)


class NextTopicsTests(TopicSetFlowTestCase):
    """What the post-assessment screen reads: the next few topics, not the graph."""

    def setUp(self):
        super().setUp()
        # A catalog larger than the next-topics cap, so the cap is observable.
        self.author_sets(
            ('deployment', 'Deployment', []),
            ('monitoring', 'Monitoring', []),
            ('security', 'Security', []),
        )
        sync_topic_skill_assessment_catalog()

    def _post_assessment_state(self, by_set_key):
        # The catalog holds eight sets, so its ceiling is eight: answering them
        # all is what lets completion through the stop rule (ADR-0003).
        session_id = self.create_session()
        response = self.save_answers(session_id, by_set_key=by_set_key, completed=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()

    def test_the_post_assessment_response_carries_at_most_five_topics(self):
        state = self._post_assessment_state(
            dict.fromkeys(('internet-and-web', 'data-storage', 'caching', 'api-design', 'testing', 'deployment', 'monitoring', 'security'), 1),
        )

        self.assertGreater(len(state['recommended_topics']), NEXT_TOPIC_COUNT)
        self.assertEqual(len(state['next_topics']), NEXT_TOPIC_COUNT)
        self.assertEqual(state['completed'], True)
        for entry in state['next_topics']:
            self.assertIn(entry['state'], ('assessed_gap', 'unassessed'))
            self.assertTrue(entry['reason'].strip())

    def test_the_next_topics_are_the_first_of_the_ordered_suggestions(self):
        state = self._post_assessment_state(
            {
                'internet-and-web': 2,
                'data-storage': 1,
                'caching': 3,
                'api-design': 1,
                'testing': 1,
                'deployment': 1,
                'monitoring': 1,
                'security': 1,
            },
        )

        self.assertEqual(
            [item['topic_slug'] for item in state['next_topics']],
            [item['topic_slug'] for item in state['recommended_topics'][:NEXT_TOPIC_COUNT]],
        )

    def test_fewer_suggestions_than_five_serve_fewer_next_topics(self):
        # Seven held, one rated below the threshold: the screen shows the one
        # suggestion that is left.
        state = self._post_assessment_state(
            {
                'internet-and-web': 5,
                'data-storage': 5,
                'caching': 5,
                'api-design': 5,
                'testing': 3,
                'deployment': 5,
                'monitoring': 5,
                'security': 5,
            },
        )

        self.assertEqual(
            [item['topic_slug'] for item in state['next_topics']],
            ['backend-developer--testing'],
        )
        self.assertEqual(state['next_topics'][0]['state'], 'assessed_gap')


class SuggestionOrderingTests(TopicSetFlowTestCase):
    def _suggested_slugs(self, state):
        return [item['topic_slug'] for item in state['recommended_topics']]

    def test_prerequisites_win_over_the_weakest_rating(self):
        # data-storage (rated 1) and api-design (rated 1) are the weakest, but
        # data-storage builds on internet-and-web and api-design on
        # data-storage, so neither comes first: internet-and-web (rated 2) and
        # caching (rated 3) sit at a shallower prerequisite layer. testing was
        # never asked about, so it follows the assessed gaps.
        session_id = self.create_session()
        response = self.save_answers(
            session_id,
            by_set_key={'internet-and-web': 2, 'data-storage': 1, 'caching': 3, 'api-design': 1},
        )
        state = response.json()

        self.assertEqual(
            self._suggested_slugs(state),
            [
                'backend-developer--internet-and-web',
                'backend-developer--caching',
                'backend-developer--data-storage',
                'backend-developer--api-design',
                'backend-developer--testing',
            ],
        )

    def test_mastery_breaks_ties_within_a_layer(self):
        # Both sets sit in no edge at the same depth; the weaker rating comes first.
        session_id = self.create_session()
        response = self.save_answers(session_id, by_set_key={'caching': 1, 'testing': 2})
        state = response.json()

        assessed = [item for item in state['recommended_topics'] if item['state'] == 'assessed_gap']
        self.assertEqual(
            [item['topic_slug'] for item in assessed],
            ['backend-developer--caching', 'backend-developer--testing'],
        )

    def test_assessed_gaps_come_before_unassessed_sets_in_prerequisite_order(self):
        session_id = self.create_session()
        response = self.save_answers(session_id, by_set_key={'data-storage': 1})
        state = response.json()

        # The assessed gap leads. Behind it, caching (no prerequisites) and
        # testing (no prerequisites) precede api-design, whose prerequisite
        # data-storage is still outstanding -- roadmap display order alone
        # would have put api-design before testing.
        self.assertEqual(
            self._suggested_slugs(state),
            [
                'backend-developer--data-storage',
                'backend-developer--internet-and-web',
                'backend-developer--caching',
                'backend-developer--testing',
                'backend-developer--api-design',
            ],
        )
        self.assertEqual([item['state'] for item in state['recommended_topics']], ['assessed_gap', *['unassessed'] * 4])

    def test_two_respondents_with_different_answers_get_different_suggestions(self):
        first = self.create_session()
        second = self.create_session()
        weak_on_data = self.save_answers(first, by_set_key={'internet-and-web': 5, 'data-storage': 1, 'caching': 5}).json()
        weak_on_caching = self.save_answers(second, by_set_key={'internet-and-web': 5, 'data-storage': 5, 'caching': 1}).json()

        self.assertEqual(self._suggested_slugs(weak_on_data)[0], 'backend-developer--data-storage')
        self.assertEqual(self._suggested_slugs(weak_on_caching)[0], 'backend-developer--caching')

    def test_reloading_returns_the_same_suggestions(self):
        session_id = self.create_session()
        self.save_answers(session_id, by_set_key={'internet-and-web': 2, 'data-storage': 1, 'caching': 3})

        first = self.get_state(session_id)
        second = self.get_state(session_id)

        self.assertEqual(self._suggested_slugs(first), self._suggested_slugs(second))
        self.assertEqual(first['recommended_topics'], second['recommended_topics'])

    def test_each_suggestion_states_why_in_terms_of_the_topics_behind_it(self):
        session_id = self.create_session()
        response = self.save_answers(session_id, by_set_key={'internet-and-web': 1, 'data-storage': 1})
        state = response.json()

        by_slug = {item['topic_slug']: item for item in state['recommended_topics']}
        self.assertIn('Internet and web protocols', by_slug['backend-developer--data-storage']['reason'])
        for item in state['recommended_topics']:
            self.assertTrue(item['reason'].strip())
