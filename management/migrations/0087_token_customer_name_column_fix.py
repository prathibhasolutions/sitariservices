from django.db import migrations


def forwards_rename_customer_number_to_customer_name(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(management_token)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'customer_number' in columns and 'customer_name' not in columns:
            cursor.execute(
                "ALTER TABLE management_token RENAME COLUMN customer_number TO customer_name"
            )


def backwards_rename_customer_name_to_customer_number(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(management_token)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'customer_name' in columns and 'customer_number' not in columns:
            cursor.execute(
                "ALTER TABLE management_token RENAME COLUMN customer_name TO customer_number"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0086_token'),
    ]

    operations = [
        migrations.RunPython(
            forwards_rename_customer_number_to_customer_name,
            backwards_rename_customer_name_to_customer_number,
        ),
    ]
