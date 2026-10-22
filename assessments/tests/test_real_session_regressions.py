from django.core.management import call_command
from django.test import TestCase

from assessments.services import scoring_service
from simulation.loaders import load_questions


SECURITY_AND_WEB_RESPONDENT = {
    'role-rd-web': 2,
    'role-rd-mobile': 1,
    'role-rd-games': 1,
    'role-rd-ai': 1,
    'role-rd-numbers': -1,
    'role-rd-security': 2,
    'role-rd-writing': -1,
    'role-rd-product': -1,
    'role-rd-weak-spots': 2,
    'role-rd-requirements': 2,
    'role-rd-evidence': 2,
    'role-rd-efficiency': 2,
    'role-rd-tie-secure-pipeline': 2,
    'role-rd-tie-investigate': 1,
    'role-rd-leading': 0,
    'role-rd-tie-model-in-production': -1,
    'role-rd-testing': 2,
    'role-rd-process': 1,
    'role-rd-explaining': 1,
    'role-rd-automation': 2,
    'role-rd-construction': 2,
    'role-rd-infrastructure': -1,
    'role-rd-ai-in-use': -1,
    'role-rd-coordination': -2,
    'role-rd-tie-train-own-model': 0,
}


class RealSessionRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('sync_content')
        cls.questions = {question['code']: question for question in load_questions()}

    def ranked_roles(self, answers):
        evidence = scoring_service.compute_role_evidence_snapshot(
            [{**self.questions[code], 'scale_value': value} for code, value in answers.items()],
        )
        return [slug for slug, _score in scoring_service.get_sorted_role_scores(evidence.role_scores)]

    def test_a_respondent_who_agrees_with_most_items_still_gets_the_roles_their_strongest_answers_point_to(self):
        ranked = self.ranked_roles(SECURITY_AND_WEB_RESPONDENT)

        self.assertIn(ranked[0], {'devsecops-engineer', 'cyber-security-engineer-analyst'})
        self.assertNotIn('machine-learning-engineer', ranked[:3])
