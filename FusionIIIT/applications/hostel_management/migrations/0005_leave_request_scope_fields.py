from django.db import migrations, models
import django.db.models.deletion


def backfill_leave_student_hall(apps, schema_editor):
    HostelLeave = apps.get_model('hostel_management', 'HostelLeave')
    Student = apps.get_model('academic_information', 'Student')
    UserHostelMapping = apps.get_model('hostel_management', 'UserHostelMapping')

    for leave in HostelLeave.objects.all():
        student = Student.objects.filter(id__user__username__iexact=leave.roll_num).first()
        if student:
            leave.student_id = student.id_id
            mapping = UserHostelMapping.objects.filter(user_id=student.id_id).first()
            if mapping:
                leave.hall_id = mapping.hall_id
            leave.save(update_fields=['student', 'hall'])


class Migration(migrations.Migration):

    dependencies = [
        ('academic_information', '0001_initial'),
        ('hostel_management', '0004_sync_notice_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='hostelleave',
            name='student',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='academic_information.student'),
        ),
        migrations.AddField(
            model_name='hostelleave',
            name='hall',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='hostel_management.hall'),
        ),
        migrations.AddField(
            model_name='hostelleave',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='hostelleave',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.RunPython(backfill_leave_student_hall, migrations.RunPython.noop),
    ]
