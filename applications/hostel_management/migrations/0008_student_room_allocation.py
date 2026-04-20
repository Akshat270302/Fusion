from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academic_information', '0001_initial'),
        ('globals', '0001_initial'),
        ('hostel_management', '0007_fix_caretaker_id_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentRoomAllocation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('assigned_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('vacated', 'Vacated')], default='active', max_length=20)),
                ('vacated_at', models.DateTimeField(blank=True, null=True)),
                ('assigned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='globals.staff')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hostel_management.hall')),
                ('room', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hostel_management.hallroom')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academic_information.student')),
            ],
            options={
                'db_table': 'hostel_management_studentroomallocation',
                'ordering': ['-assigned_at'],
            },
        ),
    ]
