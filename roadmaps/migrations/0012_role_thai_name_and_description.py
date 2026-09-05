from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('roadmaps', '0011_externalroadmapnode_externalroadmapedge_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='role',
            name='name_th',
            field=models.CharField(blank=True, default='', max_length=128),
        ),
        migrations.AddField(
            model_name='role',
            name='description_th',
            field=models.TextField(blank=True, default=''),
        ),
    ]
