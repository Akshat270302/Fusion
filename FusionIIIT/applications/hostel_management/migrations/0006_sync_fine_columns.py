from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hostel_management', '0005_leave_request_scope_fields'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE hostel_management_hostelfine
                ADD COLUMN IF NOT EXISTS caretaker_id integer NULL;

                ALTER TABLE hostel_management_hostelfine
                ADD COLUMN IF NOT EXISTS category varchar(50) NOT NULL DEFAULT 'Rule Violation';

                ALTER TABLE hostel_management_hostelfine
                ADD COLUMN IF NOT EXISTS evidence varchar(100) NULL;

                ALTER TABLE hostel_management_hostelfine
                ADD COLUMN IF NOT EXISTS created_at timestamp with time zone;

                ALTER TABLE hostel_management_hostelfine
                ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone;

                UPDATE hostel_management_hostelfine
                SET created_at = NOW()
                WHERE created_at IS NULL;

                UPDATE hostel_management_hostelfine
                SET updated_at = NOW()
                WHERE updated_at IS NULL;

                ALTER TABLE hostel_management_hostelfine
                ALTER COLUMN created_at SET NOT NULL;

                ALTER TABLE hostel_management_hostelfine
                ALTER COLUMN updated_at SET NOT NULL;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
