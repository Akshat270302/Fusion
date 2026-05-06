from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0022_room_vacation'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('globals', '0005_moduleaccess_database'),
    ]

    operations = [
        migrations.CreateModel(
            name='HostelGeneratedReport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_uid', models.CharField(blank=True, max_length=32, unique=True)),
                ('creator_role', models.CharField(default='other', max_length=20)),
                ('report_type', models.CharField(choices=[('room_occupancy', 'Room Occupancy Report'), ('attendance_summary', 'Attendance Summary Report'), ('leave_analysis', 'Leave Analysis Report'), ('fine_disciplinary', 'Fine and Disciplinary Report'), ('complaint_resolution', 'Complaint Resolution Report'), ('guest_room_booking', 'Guest Room Booking Report'), ('extended_stay', 'Extended Stay Report'), ('comprehensive', 'Comprehensive Hostel Report')], max_length=40)),
                ('title', models.CharField(max_length=200)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('filters', models.JSONField(blank=True, default=dict)),
                ('report_data', models.JSONField(blank=True, default=dict)),
                ('status', models.CharField(choices=[('Draft', 'Draft'), ('Submitted', 'Submitted'), ('Reviewed', 'Reviewed'), ('Approved', 'Approved'), ('Needs Revision', 'Needs Revision')], default='Draft', max_length=20)),
                ('priority', models.CharField(choices=[('Normal', 'Normal'), ('High', 'High'), ('Urgent', 'Urgent')], default='Normal', max_length=10)),
                ('submission_notes', models.TextField(blank=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('review_feedback', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hostel_reports_created', to='auth.user')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='generated_reports', to='hostel_management.hall')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hostel_reports_reviewed', to='auth.user')),
            ],
            options={
                'db_table': 'hostel_management_generatedreport',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='HostelReportAttachment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='hostel/reports/supporting/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attachments', to='hostel_management.hostelgeneratedreport')),
                ('uploaded_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hostel_report_attachments', to='auth.user')),
            ],
            options={
                'db_table': 'hostel_management_reportattachment',
                'ordering': ['-uploaded_at'],
            },
        ),
        migrations.CreateModel(
            name='HostelReportAuditLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(max_length=50)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='hostel_report_audit_actions', to='auth.user')),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to='hostel_management.hostelgeneratedreport')),
            ],
            options={
                'db_table': 'hostel_management_reportauditlog',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='HostelReportFilterTemplate',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('template_name', models.CharField(max_length=100)),
                ('report_type', models.CharField(choices=[('room_occupancy', 'Room Occupancy Report'), ('attendance_summary', 'Attendance Summary Report'), ('leave_analysis', 'Leave Analysis Report'), ('fine_disciplinary', 'Fine and Disciplinary Report'), ('complaint_resolution', 'Complaint Resolution Report'), ('guest_room_booking', 'Guest Room Booking Report'), ('extended_stay', 'Extended Stay Report'), ('comprehensive', 'Comprehensive Hostel Report')], max_length=40)),
                ('template_filters', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='report_templates', to='hostel_management.hall')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hostel_report_templates', to='auth.user')),
            ],
            options={
                'db_table': 'hostel_management_reportfiltertemplate',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='hostelreportfiltertemplate',
            constraint=models.UniqueConstraint(fields=('owner', 'hall', 'template_name', 'report_type'), name='unique_report_template_per_owner_hall_and_type'),
        ),
    ]
