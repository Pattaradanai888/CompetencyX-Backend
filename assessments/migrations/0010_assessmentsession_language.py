from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0009_survey2dimension_survey2roleguidance'),
    ]

    operations = [
        migrations.AddField(
            model_name='assessmentsession',
            name='language',
            field=models.CharField(choices=[('en', 'English'), ('th', 'Thai')], default='en', max_length=8),
        ),
    ]
