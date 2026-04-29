from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roadmaps', '0003_remove_questionoption_mastery_value_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='discriminates_between',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='question',
            name='item_group',
            field=models.CharField(
                choices=[('core', 'Core'), ('tie_break', 'Tie Break'), ('standard', 'Standard')],
                default='standard',
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name='questionoption',
            name='dimension_signals',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
