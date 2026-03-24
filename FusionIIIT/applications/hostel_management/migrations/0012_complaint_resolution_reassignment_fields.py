from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0011_complaint_escalation_fields'),
        ('globals', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='hostelcomplaint',
            name='resolution_notes',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Notes on how the complaint was resolved',
            ),
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='resolved_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the complaint was resolved',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='resolved_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Warden who resolved the complaint',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='resolved_complaints',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='reassigned_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the complaint was reassigned',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='reassigned_to',
            field=models.ForeignKey(
                blank=True,
                help_text='Caretaker complaint was reassigned to',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='reassigned_complaints',
                to='globals.staff',
            ),
        ),
        migrations.AddField(
            model_name='hostelcomplaint',
            name='reassignment_instructions',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Instructions for caretaker on reassignment',
            ),
        ),
    ]
