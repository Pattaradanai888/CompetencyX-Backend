from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0011_merged_language_and_survey2_qvalue'),
    ]

    operations = [
        migrations.DeleteModel(
            name='QuestionSelectionEvent',
        ),
        migrations.DeleteModel(
            name='QuestionBanditStat',
        ),
    ]
