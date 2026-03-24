from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def backfill_attendance_status(apps, schema_editor):
    attendance_model = apps.get_model('hostel_management', 'HostelStudentAttendence')
    for record in attendance_model.objects.all().iterator():
        record.status = 'present' if record.present else 'absent'
        record.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('globals', '0001_initial'),
        ('hostel_management', '0008_student_room_allocation'),
    ]

    operations = [
        migrations.AddField(
            model_name='hostelstudentattendence',
            name='status',
            field=models.CharField(
                choices=[('present', 'Present'), ('absent', 'Absent')],
                default='present',
                max_length=10,
            ),
        ),
        migrations.RunPython(backfill_attendance_status, migrations.RunPython.noop),
        migrations.AddField(
            model_name='hostelstudentattendence',
            name='marked_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='hostel_attendance_marked',
                to='globals.staff',
            ),
        ),
        migrations.AddField(
            model_name='hostelstudentattendence',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name='hostelstudentattendence',
            constraint=models.UniqueConstraint(fields=('student_id', 'date'), name='unique_hostel_attendance_student_date'),
        ),
        migrations.AlterModelOptions(
            name='hostelstudentattendence',
            options={'ordering': ['-date', 'student_id__id__user__username']},
        ),
    ]
