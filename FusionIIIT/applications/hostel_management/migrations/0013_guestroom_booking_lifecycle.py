from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('globals', '0005_moduleaccess_database'),
        ('hostel_management', '0012_complaint_resolution_reassignment_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='guestroom',
            name='room_status',
            field=models.CharField(
                choices=[
                    ('Booked', 'Booked'),
                    ('CheckedIn', 'Checked In'),
                    ('Available', 'Available'),
                    ('UnderMaintenance', 'Under Maintenance'),
                ],
                default='Available',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='booking_charge_per_day',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='cancel_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='canceled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='checkin_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='checked_in_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='checked_out_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='completed_with_damages',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='damage_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='damage_report',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='decision_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='decision_comment',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='id_proof_number',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='id_proof_type',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='inspection_notes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='last_modified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='modified_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='total_charge',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='checked_in_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='guestroom_booking_checkins',
                to='globals.staff',
            ),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='checked_out_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='guestroom_booking_checkouts',
                to='globals.staff',
            ),
        ),
        migrations.AddField(
            model_name='guestroombooking',
            name='decision_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='guestroom_booking_decisions',
                to='globals.staff',
            ),
        ),
        migrations.CreateModel(
            name='GuestRoomPolicy',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feature_enabled', models.BooleanField(default=True)),
                ('charge_per_day', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('min_advance_days', models.PositiveIntegerField(default=0)),
                ('max_advance_days', models.PositiveIntegerField(default=90)),
                ('max_booking_duration_days', models.PositiveIntegerField(default=7)),
                ('max_concurrent_bookings_per_student', models.PositiveIntegerField(default=1)),
                ('eligibility_note', models.CharField(blank=True, max_length=255)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'hall',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='guest_room_policy',
                        to='hostel_management.hall',
                    ),
                ),
            ],
            options={
                'db_table': 'hostel_management_guestroompolicy',
            },
        ),
    ]
