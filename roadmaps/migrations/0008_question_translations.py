from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roadmaps', '0007_question_agree_disagree_signals'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='translations',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
