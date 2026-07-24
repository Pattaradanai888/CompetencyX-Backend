from assessments.models import SkillAssessmentDimension, SkillAssessmentQuestion, SkillAssessmentRoleGuidance
from assessments.skill_assessment_seed_data import SKILL_ASSESSMENT_DIMENSIONS, SKILL_ASSESSMENT_QUESTIONS, SKILL_ASSESSMENT_ROLE_GUIDANCE
from roadmaps.models import Role


def sync_skill_assessment_catalog(*, stdout=None):
    dimension_keys = []
    for dimension in SKILL_ASSESSMENT_DIMENSIONS:
        dimension_keys.append(dimension['dimension_key'])
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
    SkillAssessmentDimension.objects.exclude(dimension_key__in=dimension_keys).update(is_active=False)

    question_ids = []
    for question in SKILL_ASSESSMENT_QUESTIONS:
        question_ids.append(question['question_id'])
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
    SkillAssessmentQuestion.objects.exclude(question_id__in=question_ids).update(is_active=False)

    guidance_count = 0
    guidance_ids = []
    role_slugs = [slug for slug in SKILL_ASSESSMENT_ROLE_GUIDANCE if slug]
    roles_by_slug = {role.slug: role for role in Role.objects.filter(slug__in=role_slugs)}
    for role_slug, guidance_items in SKILL_ASSESSMENT_ROLE_GUIDANCE.items():
        role = roles_by_slug.get(role_slug) if role_slug else None
        if role_slug and role is None:
            if stdout is not None:
                stdout.write(f'Skipping Skill Assessment guidance for missing role "{role_slug}".')
            continue

        for display_order, guidance in enumerate(guidance_items, start=1):
            guidance_item, _created = SkillAssessmentRoleGuidance.objects.update_or_create(
                role=role,
                display_order=display_order,
                defaults={'guidance': guidance, 'is_active': True},
            )
            guidance_ids.append(guidance_item.id)
            guidance_count += 1
    SkillAssessmentRoleGuidance.objects.exclude(id__in=guidance_ids).update(is_active=False)

    if stdout is not None:
        stdout.write(
            f'Synced Skill Assessment catalog: {len(SKILL_ASSESSMENT_DIMENSIONS)} dimensions, '
            f'{len(SKILL_ASSESSMENT_QUESTIONS)} questions, and {guidance_count} guidance rows.'
        )
