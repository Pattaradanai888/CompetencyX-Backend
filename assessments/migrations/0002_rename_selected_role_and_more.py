from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('assessments', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='assessmentsession',
            old_name='selected_role',
            new_name='preferred_role',
        ),
        migrations.RenameField(
            model_name='assessmentsession',
            old_name='inferred_role',
            new_name='best_fit_role',
        ),
        migrations.RenameField(
            model_name='assessmentsession',
            old_name='role_confidence',
            new_name='best_fit_confidence',
        ),
    ]
