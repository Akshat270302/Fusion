from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0016_hall_operational_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='hallcaretaker',
            name='assigned_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='hallcaretaker',
            name='end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hallcaretaker',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='hallcaretaker',
            name='start_date',
            field=models.DateField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='hallwarden',
            name='assigned_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='hallwarden',
            name='assignment_role',
            field=models.CharField(choices=[('primary', 'Primary'), ('secondary', 'Secondary')], default='primary', max_length=20),
        ),
        migrations.AddField(
            model_name='hallwarden',
            name='end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hallwarden',
            name='is_active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='hallwarden',
            name='start_date',
            field=models.DateField(default=django.utils.timezone.now),
        ),
    ]
