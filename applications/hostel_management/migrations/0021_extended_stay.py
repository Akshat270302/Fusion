from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('globals', '0005_moduleaccess_database'),
        ('hostel_management', '0020_hostel_room_groups'),
        ('academic_information', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExtendedStay',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('reason', models.TextField()),
                ('faculty_authorization', models.TextField()),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('Pending', 'Pending'),
                            ('Approved', 'Approved'),
                            ('Rejected', 'Rejected'),
                            ('Cancelled', 'Cancelled'),
                        ],
                        default='Pending',
                        max_length=20,
                    ),
                ),
                (
                    'caretaker_decision',
                    models.CharField(
                        choices=[
                            ('Pending', 'Pending'),
                            ('Approved', 'Approved'),
                            ('Rejected', 'Rejected'),
                        ],
                        default='Pending',
                        max_length=20,
                    ),
                ),
                ('caretaker_remarks', models.TextField(blank=True)),
                ('caretaker_decided_at', models.DateTimeField(blank=True, null=True)),
                (
                    'warden_decision',
                    models.CharField(
                        choices=[
                            ('Pending', 'Pending'),
                            ('Approved', 'Approved'),
                            ('Rejected', 'Rejected'),
                        ],
                        default='Pending',
                        max_length=20,
                    ),
                ),
                ('warden_remarks', models.TextField(blank=True)),
                ('warden_decided_at', models.DateTimeField(blank=True, null=True)),
                ('cancel_reason', models.TextField(blank=True)),
                ('canceled_at', models.DateTimeField(blank=True, null=True)),
                ('modified_count', models.PositiveIntegerField(default=0)),
                ('last_modified_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'caretaker_decided_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='extended_stay_caretaker_decisions',
                        to='globals.staff',
                    ),
                ),
                (
                    'hall',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='extended_stays',
                        to='hostel_management.hall',
                    ),
                ),
                (
                    'requested_by',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='extended_stay_requests',
                        to='auth.user',
                    ),
                ),
                (
                    'student',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='extended_stays',
                        to='academic_information.student',
                    ),
                ),
                (
                    'warden_decided_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='extended_stay_warden_decisions',
                        to='globals.faculty',
                    ),
                ),
            ],
            options={
                'db_table': 'hostel_management_extendedstay',
                'ordering': ['-created_at'],
            },
        ),
    ]
