from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0021_extended_stay'),
        ('academic_information', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('globals', '0005_moduleaccess_database'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoomVacationRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('intended_vacation_date', models.DateField()),
                ('reason', models.TextField()),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('Pending Clearance', 'Pending Clearance'),
                            ('Clearance Approved', 'Clearance Approved'),
                            ('Clearance Pending - Action Required', 'Clearance Pending - Action Required'),
                            ('Completed', 'Completed'),
                        ],
                        default='Pending Clearance',
                        max_length=50,
                    ),
                ),
                ('checklist_generated_at', models.DateTimeField(blank=True, null=True)),
                ('checklist_acknowledged', models.BooleanField(default=False)),
                ('checklist_acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('room_inspection_notes', models.TextField(blank=True)),
                ('room_damages_found', models.BooleanField(default=False)),
                ('room_damage_description', models.TextField(blank=True)),
                ('room_damage_fine_amount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('caretaker_review_comments', models.TextField(blank=True)),
                ('borrowed_items_notes', models.TextField(blank=True)),
                ('behavior_notes', models.TextField(blank=True)),
                ('clearance_certificate_no', models.CharField(blank=True, max_length=40, null=True, unique=True)),
                ('clearance_approved_at', models.DateTimeField(blank=True, null=True)),
                ('finalized_at', models.DateTimeField(blank=True, null=True)),
                ('completion_report', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'allocation',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='vacation_requests',
                        to='hostel_management.studentroomallocation',
                    ),
                ),
                (
                    'clearance_approved_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='approved_vacation_clearances',
                        to='globals.staff',
                    ),
                ),
                (
                    'finalized_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='finalized_room_vacations',
                        to='auth.user',
                    ),
                ),
                (
                    'hall',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='room_vacation_requests',
                        to='hostel_management.hall',
                    ),
                ),
                (
                    'requested_by',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='room_vacation_requests',
                        to='auth.user',
                    ),
                ),
                (
                    'student',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='room_vacation_requests',
                        to='academic_information.student',
                    ),
                ),
            ],
            options={
                'db_table': 'hostel_management_roomvacationrequest',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='RoomVacationChecklistItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=50)),
                ('title', models.CharField(max_length=120)),
                ('details', models.TextField(blank=True)),
                ('is_blocking', models.BooleanField(default=False)),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('Pending', 'Pending'),
                            ('Verified', 'Verified'),
                            ('Pending Action', 'Pending Action'),
                        ],
                        default='Pending',
                        max_length=20,
                    ),
                ),
                ('caretaker_comment', models.TextField(blank=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'request',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='checklist_items',
                        to='hostel_management.roomvacationrequest',
                    ),
                ),
            ],
            options={
                'db_table': 'hostel_management_roomvacationchecklistitem',
                'ordering': ['id'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('request', 'code'),
                        name='unique_vacation_checklist_code_per_request',
                    ),
                ],
            },
        ),
    ]
