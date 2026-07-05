from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('assessments', '0013_remove_survey1_skill_assessment'),
    ]

    operations = [
        migrations.DeleteModel('TopicMastery'),
    ]
