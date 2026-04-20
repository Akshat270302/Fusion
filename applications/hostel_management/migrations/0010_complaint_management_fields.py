# Generated migration for complaint management system
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('academic_information', '0001_initial'),
        ('globals', '0001_initial'),
        ('hostel_management', '0009_attendance_submission_fields'),
    ]

    operations = [
        # Add ComplaintStatus choice
        migrations.AddField(
            model_name='hostelcomplaint',
            name='student',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='academic_information.student',
            ),
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='hall',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='hostel_management.hall',
            ),
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='title',
            field=models.CharField(default='', blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('resolved', 'Resolved')],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Remove old fields
        migrations.RemoveField(
            model_name='hostelcomplaint',
            name='hall_name',
        ),
        migrations.RemoveField(
            model_name='hostelcomplaint',
            name='student_name',
        ),
        migrations.RemoveField(
            model_name='hostelcomplaint',
            name='roll_number',
        ),
        migrations.RemoveField(
            model_name='hostelcomplaint',
            name='contact_number',
        ),
        # Update model options
        migrations.AlterModelOptions(
            name='hostelcomplaint',
            options={
                'ordering': ['-created_at'],
                'db_table': 'hostel_management_hostelcomplaint'
            },
        ),
        # Add unique constraint
        migrations.AddConstraint(
            model_name='hostelcomplaint',
            constraint=models.UniqueConstraint(
                fields=['student', 'title', 'created_at'],
                name='unique_hostel_complaint_student_title_date'
            ),
        ),
    ]
