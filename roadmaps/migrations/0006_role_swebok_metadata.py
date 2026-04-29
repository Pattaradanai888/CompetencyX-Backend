from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('roadmaps', '0005_remove_questionoption_dimension_signals_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='core_tasks',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='role',
            name='swebok_source_version',
            field=models.CharField(blank=True, max_length=32),
        ),
        migrations.AddField(
            model_name='role',
            name='top_ka_codes',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
