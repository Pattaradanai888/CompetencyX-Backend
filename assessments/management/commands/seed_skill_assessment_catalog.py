from django.core.management.base import BaseCommand

from assessments.models import SkillAssessmentDimension, SkillAssessmentQuestion, SkillAssessmentRoleGuidance
from assessments.skill_assessment_seed_data import SKILL_ASSESSMENT_DIMENSIONS, SKILL_ASSESSMENT_QUESTIONS, SKILL_ASSESSMENT_ROLE_GUIDANCE
from roadmaps.models import Role


class Command(BaseCommand):
    help = 'Seed or refresh the Skill Assessment catalog tables in the database.'

    def handle(self, *args, **options):
        dimension_count = 0
        question_count = 0
        guidance_count = 0

        for dimension in SKILL_ASSESSMENT_DIMENSIONS:
            SkillAssessmentDimension.objects.update_or_create(
                dimension_key=dimension['dimension_key'],
                defaults={
                    'label': dimension['label'],
                    'track': dimension['track'],
                    'low_score_action': dimension['low_score_action'],
                    'translations': dimension.get('translations', {}),
                    'display_order': dimension['display_order'],
                    'is_active': True,
                },
            )
            dimension_count += 1

        for question in SKILL_ASSESSMENT_QUESTIONS:
            SkillAssessmentQuestion.objects.update_or_create(
                question_id=question['question_id'],
                defaults={
                    'prompt': question['prompt'],
                    'translations': question.get('translations', {}),
                    'dimension_key': question['dimension_key'],
                    'display_order': question['display_order'],
                    'is_active': True,
                },
            )
            question_count += 1

        for role_slug, guidance_items in SKILL_ASSESSMENT_ROLE_GUIDANCE.items():
            role = None
            if role_slug is not None:
                role = Role.objects.filter(slug=role_slug).first()
                if role is None:
                    self.stdout.write(
                        self.style.WARNING(f'Skipping Skill Assessment guidance for missing role "{role_slug}".'),
                    )
                    continue

            for display_order, guidance in enumerate(guidance_items, start=1):
                SkillAssessmentRoleGuidance.objects.update_or_create(
                    role=role,
                    display_order=display_order,
                    defaults={
                        'guidance': guidance,
                        'is_active': True,
                    },
                )
                guidance_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Seeded Skill Assessment catalog: {dimension_count} dimensions, {question_count} questions, {guidance_count} guidance rows.',
            ),
        )
