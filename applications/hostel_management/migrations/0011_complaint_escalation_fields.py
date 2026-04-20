# Generated migration for escalation feature

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0010_complaint_management_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Add new status choice 'escalated' to ComplaintStatus enum
        migrations.AlterField(
            model_name='hostelcomplaint',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('in_progress', 'In Progress'),
                    ('escalated', 'Escalated'),
                    ('resolved', 'Resolved'),
                ],
                default='pending',
                max_length=20
            ),
        ),
        # Add escalation_reason field
        migrations.AddField(
            model_name='hostelcomplaint',
            name='escalation_reason',
            field=models.TextField(blank=True, default='', help_text='Reason for escalating to warden'),
        ),
        # Add escalated_by field
        migrations.AddField(
            model_name='hostelcomplaint',
            name='escalated_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Caretaker who escalated the complaint',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='escalated_complaints',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Add escalated_at field
        migrations.AddField(
            model_name='hostelcomplaint',
            name='escalated_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the complaint was escalated',
                null=True,
            ),
        ),
    ]
