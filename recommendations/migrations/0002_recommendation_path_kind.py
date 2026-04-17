from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('recommendations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='recommendation',
            name='path_kind',
            field=models.CharField(
                choices=[('preferred', 'Preferred Role Path'), ('best_fit', 'Best-Fit Role Path')],
                default='preferred',
                max_length=24,
            ),
        ),
    ]
