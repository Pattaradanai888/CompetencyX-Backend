from django.db import migrations, models
from django.utils import timezone


def remove_survey1_skill_assessment(apps, schema_editor):
    AssessmentSession = apps.get_model('assessments', 'AssessmentSession')
    TopicMastery = apps.get_model('assessments', 'TopicMastery')
    Question = apps.get_model('roadmaps', 'Question')

    TopicMastery.objects.all().delete()
    Question.objects.filter(stage='skill').delete()
    AssessmentSession.objects.filter(phase='skill_assessment').update(
        phase='recommendation_ready',
        status='completed',
        completed_at=timezone.now(),
    )


class Migration(migrations.Migration):
    dependencies = [
        ('assessments', '0012_drop_selection_event_and_bandit_stat'),
        ('roadmaps', '0008_question_translations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assessmentsession',
            name='phase',
            field=models.CharField(
                choices=[
                    ('role_discovery', 'Role Discovery'),
                    ('role_ambiguity', 'Role Ambiguity'),
                    ('recommendation_ready', 'Recommendation Ready'),
                    ('completed', 'Completed'),
                ],
                default='role_discovery',
                max_length=32,
            ),
        ),
        migrations.RunPython(remove_survey1_skill_assessment, reverse_code=migrations.RunPython.noop),
    ]
