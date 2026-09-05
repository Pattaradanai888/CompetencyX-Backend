# ADR-0005: the role-independent PSP/SDLC items are retired, and Recommendation
# Stability is recomputed from the answers rather than stored between saves.

from django.db import migrations


def retire_role_independent_items(apps, schema_editor):
    SkillAssessmentQuestion = apps.get_model('assessments', 'SkillAssessmentQuestion')
    SkillAssessmentDimension = apps.get_model('assessments', 'SkillAssessmentDimension')
    # Answers recorded against these items keep their rows: the answer table is
    # keyed by the catalog slug rather than a foreign key for exactly this case.
    SkillAssessmentQuestion.objects.filter(role__isnull=True).delete()
    SkillAssessmentDimension.objects.filter(role__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('assessments', '0007_held_topic_marks'),
    ]

    operations = [
        migrations.RunPython(retire_role_independent_items, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='skillassessmentdimension',
            name='track',
        ),
        migrations.RemoveField(
            model_name='assessmentsession',
            name='skill_assessment_top_five',
        ),
        migrations.RemoveField(
            model_name='assessmentsession',
            name='skill_assessment_stable',
        ),
    ]
