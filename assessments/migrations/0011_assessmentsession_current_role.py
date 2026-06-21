from django.db import migrations, models

import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0010_assessmentsession_language'),
        ('assessments', '0010_survey2questionqvalue'),
    ]

    operations = [
        migrations.AddField(
            model_name='assessmentsession',
            name='current_role',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='current_sessions', to='roadmaps.role'),
        ),
    ]
