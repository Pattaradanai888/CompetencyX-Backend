from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roadmaps', '0006_role_swebok_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='agree_dimension_signals',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='question',
            name='disagree_dimension_signals',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
