from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='hostelnoticeboard',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='hostelnoticeboard',
            name='role',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
