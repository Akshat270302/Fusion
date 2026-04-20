from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0018_hostel_batch'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HostelLifecycleState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_step', models.PositiveSmallIntegerField(default=1)),
                ('staff_assigned', models.BooleanField(default=False)),
                ('rooms_configured', models.BooleanField(default=False)),
                ('hostel_activated', models.BooleanField(default=False)),
                ('batch_assigned', models.BooleanField(default=False)),
                ('eligible_students_fetched', models.BooleanField(default=False)),
                ('bulk_allotment_completed', models.BooleanField(default=False)),
                ('occupancy_updated', models.BooleanField(default=False)),
                ('notifications_sent', models.BooleanField(default=False)),
                ('operational', models.BooleanField(default=False)),
                ('last_transition_note', models.CharField(blank=True, max_length=255)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('hall', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='lifecycle_state', to='hostel_management.hall')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'hostel_management_hostellifecyclestate',
                'ordering': ['hall__hall_id'],
            },
        ),
    ]
