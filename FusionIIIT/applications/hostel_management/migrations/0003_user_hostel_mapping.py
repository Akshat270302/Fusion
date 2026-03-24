from django.db import migrations, models
import django.db.models.deletion


def populate_user_hostel_mapping(apps, schema_editor):
    UserHostelMapping = apps.get_model('hostel_management', 'UserHostelMapping')
    Hall = apps.get_model('hostel_management', 'Hall')
    HallWarden = apps.get_model('hostel_management', 'HallWarden')
    HallCaretaker = apps.get_model('hostel_management', 'HallCaretaker')
    StudentDetails = apps.get_model('hostel_management', 'StudentDetails')

    for assignment in HallWarden.objects.all():
        if assignment.faculty_id and assignment.hall_id:
            UserHostelMapping.objects.update_or_create(
                user_id=assignment.faculty_id,
                defaults={'hall_id': assignment.hall_id, 'role': 'warden'},
            )

    for assignment in HallCaretaker.objects.all():
        if assignment.staff_id and assignment.hall_id:
            UserHostelMapping.objects.update_or_create(
                user_id=assignment.staff_id,
                defaults={'hall_id': assignment.hall_id, 'role': 'caretaker'},
            )

    for student in StudentDetails.objects.exclude(hall_id__isnull=True).exclude(hall_id=''):
        hall = Hall.objects.filter(hall_id=student.hall_id).first()
        if not hall:
            continue

        UserHostelMapping.objects.get_or_create(
            user_id=student.id,
            defaults={'hall_id': hall.id, 'role': 'student'},
        )


def reverse_user_hostel_mapping(apps, schema_editor):
    UserHostelMapping = apps.get_model('hostel_management', 'UserHostelMapping')
    UserHostelMapping.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('globals', '0005_moduleaccess_database'),
        ('hostel_management', '0002_notice_role_created_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserHostelMapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('student', 'Student'), ('warden', 'Warden'), ('caretaker', 'Caretaker'), ('other', 'Other')], default='other', max_length=20)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mapped_users', to='hostel_management.Hall')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='hostel_mapping', to='globals.ExtraInfo')),
            ],
            options={
                'db_table': 'hostel_management_userhostelmapping',
                'ordering': ['user_id'],
            },
        ),
        migrations.RunPython(populate_user_hostel_mapping, reverse_user_hostel_mapping),
    ]
