from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0006_sync_fine_columns'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE hostel_management_hostelfine
                ALTER COLUMN caretaker_id TYPE varchar(20)
                USING caretaker_id::varchar;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
