from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0003_user_hostel_mapping'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE hostel_management_hostelnoticeboard
                ADD COLUMN IF NOT EXISTS role varchar(20) NOT NULL DEFAULT '';

                ALTER TABLE hostel_management_hostelnoticeboard
                ADD COLUMN IF NOT EXISTS created_at timestamp with time zone;

                UPDATE hostel_management_hostelnoticeboard
                SET created_at = NOW()
                WHERE created_at IS NULL;

                ALTER TABLE hostel_management_hostelnoticeboard
                ALTER COLUMN created_at SET NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
