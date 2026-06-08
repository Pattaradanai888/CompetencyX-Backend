from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('assessments', '0009_survey2dimension_survey2roleguidance'),
    ]

    operations = [
        migrations.CreateModel(
            name='Survey2QuestionQValue',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('state_key', models.CharField(max_length=255)),
                ('question_id', models.SlugField(max_length=64)),
                ('q_value', models.FloatField(default=0.0)),
                ('reward_total', models.FloatField(default=0.0)),
                ('update_count', models.PositiveIntegerField(default=0)),
                ('last_reward', models.FloatField(default=0.0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['state_key', 'question_id'],
                'unique_together': {('state_key', 'question_id')},
            },
        ),
    ]
