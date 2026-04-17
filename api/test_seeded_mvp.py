from django.core.management import call_command
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from roadmaps.models import Question, Role


EXPECTED_SEEDED_ROLE_COUNT = 8
MIN_ROLE_QUESTION_COUNT = 2
PRIMARY_ROLE_OPTION_KEYS = {
    'frontend-engineer': 'frontend',
    'backend-engineer': 'backend',
    'full-stack-engineer': 'fullstack',
    'devops-engineer': 'devops',
    'data-engineer': 'data',
    'mobile-engineer': 'mobile',
    'qa-test-engineer': 'qa',
    'cybersecurity-engineer': 'security',
}
SECONDARY_ROLE_OPTION_KEYS = {
    'frontend-engineer': 'ui-behavior',
    'backend-engineer': 'service-logic',
    'full-stack-engineer': 'service-logic',
    'devops-engineer': 'reliability',
    'data-engineer': 'data-systems',
    'mobile-engineer': 'ui-behavior',
    'qa-test-engineer': 'reliability',
    'cybersecurity-engineer': 'risk-defense',
}


class SeededMvpFlowTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_mvp_content')

    def test_all_seeded_roles_are_exposed_in_catalog(self):
        response = self.client.get(reverse('role-list'))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == EXPECTED_SEEDED_ROLE_COUNT

    def test_all_seeded_roles_can_complete_preferred_role_assessment(self):
        role_questions = list(Question.objects.filter(stage=Question.Stage.ROLE).order_by('display_order'))
        assert len(role_questions) >= MIN_ROLE_QUESTION_COUNT

        for role_slug in Role.objects.order_by('slug').values_list('slug', flat=True):
            create_response = self.client.post(
                reverse('assessment-session-create'),
                {'preferred_role_slug': role_slug},
                format='json',
            )

            assert create_response.status_code == status.HTTP_201_CREATED
            payload = create_response.json()
            current_question = payload['current_question']

            role_option_keys = (
                PRIMARY_ROLE_OPTION_KEYS[role_slug],
                SECONDARY_ROLE_OPTION_KEYS[role_slug],
            )
            for option_key in role_option_keys:
                option_id = Question.objects.get(id=current_question['id']).options.get(key=option_key).id
                answer_response = self.client.post(
                    reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                    {'question_id': current_question['id'], 'option_id': option_id},
                    format='json',
                )
                assert answer_response.status_code == status.HTTP_200_OK
                payload = answer_response.json()
                current_question = payload['current_question']

            while current_question is not None:
                yes_option_id = Question.objects.get(id=current_question['id']).options.get(key='yes').id
                answer_response = self.client.post(
                    reverse('assessment-answer-submit', kwargs={'pk': payload['id']}),
                    {'question_id': current_question['id'], 'option_id': yes_option_id},
                    format='json',
                )
                assert answer_response.status_code == status.HTTP_200_OK
                payload = answer_response.json()
                current_question = payload['current_question']

            assert payload['phase'] == 'recommendation_ready'
            results_response = self.client.get(reverse('assessment-session-results', kwargs={'pk': payload['id']}))
            assert results_response.status_code == status.HTTP_200_OK
            assert results_response.json()['preferred_path_recommendation'] is not None
            assert results_response.json()['preferred_path_recommendation']['topic_slug'] is not None
