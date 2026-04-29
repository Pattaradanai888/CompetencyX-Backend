from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0004_questionselectionevent_questionbanditstat'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionselectionevent',
            name='candidate_scores',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='questionselectionevent',
            name='selection_score',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='questionselectionevent',
            name='policy_mode',
            field=models.CharField(
                choices=[
                    ('heuristic', 'Heuristic'),
                    ('info_gain', 'Information Gain'),
                    ('shadow_bandit', 'Shadow Bandit'),
                    ('live_bandit', 'Live Bandit'),
                ],
                max_length=24,
            ),
        ),
    ]
