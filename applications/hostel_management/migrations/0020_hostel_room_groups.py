from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0019_hostel_lifecycle_state'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('academic_information', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='HostelRoomGroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_auto_generated', models.BooleanField(default=False)),
                ('member_signature', models.CharField(max_length=255)),
                ('allotted_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('allotted_room', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='allotted_groups', to='hostel_management.hallroom')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='room_groups', to='hostel_management.hall')),
            ],
            options={
                'db_table': 'hostel_management_hostelroomgroup',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='HostelRoomGroupMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='hostel_management.hostelroomgroup')),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='hostel_group_membership', to='academic_information.student')),
            ],
            options={
                'db_table': 'hostel_management_hostelroomgroupmember',
                'ordering': ['group_id', 'student_id'],
            },
        ),
        migrations.AddConstraint(
            model_name='hostelroomgroup',
            constraint=models.UniqueConstraint(fields=('hall', 'member_signature'), name='unique_hostel_group_signature_per_hall'),
        ),
        migrations.AddConstraint(
            model_name='hostelroomgroupmember',
            constraint=models.UniqueConstraint(fields=('group', 'student'), name='unique_student_in_same_group'),
        ),
    ]
