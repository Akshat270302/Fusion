# Generated manually for room change request workflow (HM-UC-013/014/015)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('academic_information', '0001_initial'),
        ('globals', '0001_initial'),
        ('hostel_management', '0013_guestroom_booking_lifecycle'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoomChangeRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_id', models.CharField(blank=True, max_length=32, unique=True)),
                ('current_room_no', models.CharField(blank=True, max_length=30)),
                ('current_hall_id', models.CharField(blank=True, max_length=20)),
                ('reason', models.TextField()),
                ('preferred_room', models.CharField(blank=True, max_length=30)),
                ('preferred_hall', models.CharField(blank=True, max_length=20)),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected'), ('Allocated', 'Allocated')], default='Pending', max_length=20)),
                ('caretaker_decision', models.CharField(choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending', max_length=20)),
                ('caretaker_remarks', models.TextField(blank=True)),
                ('caretaker_decided_at', models.DateTimeField(blank=True, null=True)),
                ('warden_decision', models.CharField(choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending', max_length=20)),
                ('warden_remarks', models.TextField(blank=True)),
                ('warden_decided_at', models.DateTimeField(blank=True, null=True)),
                ('allocation_notes', models.TextField(blank=True)),
                ('allocated_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('allocated_room', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='hostel_management.hallroom')),
                ('caretaker_decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='room_change_caretaker_decisions', to='globals.staff')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hostel_management.hall')),
                ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='academic_information.student')),
                ('warden_decided_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='room_change_warden_decisions', to='globals.faculty')),
            ],
            options={
                'db_table': 'hostel_management_roomchangerequest',
                'ordering': ['-created_at'],
            },
        ),
    ]
