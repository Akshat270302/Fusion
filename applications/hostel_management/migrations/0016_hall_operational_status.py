from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0015_inventory_workflow'),
    ]

    operations = [
        migrations.AddField(
            model_name='hall',
            name='operational_status',
            field=models.CharField(
                choices=[
                    ('Active', 'Active'),
                    ('Inactive', 'Inactive'),
                    ('UnderMaintenance', 'Under Maintenance'),
                ],
                default='Inactive',
                max_length=20,
            ),
        ),
    ]
