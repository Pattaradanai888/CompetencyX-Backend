"""Synchronise the Skill Assessment role guidance.

The items and dimensions of the Skill Assessment are generated per role from
its Assessable Topic Sets (see ``topic_skill_assessment_service``); the only
authored content that still lives here is the per-role guidance shown beside
the assessment. The role-independent PSP/SDLC items that used to be seeded
alongside it were retired once every role had authored sets (ADR-0005).
"""

from assessments.models import SkillAssessmentRoleGuidance
from assessments.skill_assessment_seed_data import SKILL_ASSESSMENT_ROLE_GUIDANCE
from roadmaps.models import Role


def sync_skill_assessment_catalog(*, stdout=None):
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
        stdout.write(f'Synced Skill Assessment guidance: {guidance_count} rows.')
