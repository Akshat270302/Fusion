# Generated manually for inventory management workflows (HM-UC-026/027/028)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('academic_information', '0001_initial'),
        ('globals', '0001_initial'),
        ('hostel_management', '0014_room_change_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='hostelinventory',
            name='condition_status',
            field=models.CharField(
                choices=[('Good', 'Good'), ('Damaged', 'Damaged'), ('Missing', 'Missing'), ('Depleted', 'Depleted')],
                default='Good',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='HostelInventoryInspection',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('remarks', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('caretaker', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='globals.staff')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hostel_management.hall')),
            ],
            options={
                'db_table': 'hostel_management_hostelinventoryinspection',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='HostelInventoryInspectionItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expected_quantity', models.PositiveIntegerField(default=0)),
                ('observed_quantity', models.PositiveIntegerField(default=0)),
                ('observed_condition', models.CharField(choices=[('Good', 'Good'), ('Damaged', 'Damaged'), ('Missing', 'Missing'), ('Depleted', 'Depleted')], default='Good', max_length=20)),
                ('discrepancy', models.BooleanField(default=False)),
                ('discrepancy_remarks', models.TextField(blank=True)),
                ('inspection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='hostel_management.hostelinventoryinspection')),
                ('inventory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hostel_management.hostelinventory')),
            ],
            options={
                'db_table': 'hostel_management_hostelinventoryinspectionitem',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='HostelResourceRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_type', models.CharField(choices=[('Replacement', 'Replacement'), ('New', 'New'), ('Additional', 'Additional')], max_length=20)),
                ('justification', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected'), ('Fulfilled', 'Fulfilled')], default='Pending', max_length=20)),
                ('review_remarks', models.TextField(blank=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('caretaker', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='globals.staff')),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hostel_management.hall')),
                ('reviewed_by_admin', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_requests_reviewed_by_admin', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by_warden', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_requests_reviewed_by_warden', to='globals.faculty')),
            ],
            options={
                'db_table': 'hostel_management_hostelresourcerequest',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='HostelResourceRequestItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_name', models.CharField(max_length=120)),
                ('requested_quantity', models.PositiveIntegerField(default=1)),
                ('remarks', models.TextField(blank=True)),
                ('inventory', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='hostel_management.hostelinventory')),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='hostel_management.hostelresourcerequest')),
            ],
            options={
                'db_table': 'hostel_management_hostelresourcerequestitem',
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='HostelInventoryUpdateLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('previous_quantity', models.IntegerField(default=0)),
                ('new_quantity', models.IntegerField(default=0)),
                ('previous_condition', models.CharField(choices=[('Good', 'Good'), ('Damaged', 'Damaged'), ('Missing', 'Missing'), ('Depleted', 'Depleted')], default='Good', max_length=20)),
                ('new_condition', models.CharField(choices=[('Good', 'Good'), ('Damaged', 'Damaged'), ('Missing', 'Missing'), ('Depleted', 'Depleted')], default='Good', max_length=20)),
                ('reason', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('hall', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hostel_management.hall')),
                ('inventory', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hostel_management.hostelinventory')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'hostel_management_hostelinventoryupdatelog',
                'ordering': ['-created_at'],
            },
        ),
    ]
