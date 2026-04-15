from django.db import migrations, models


def ensure_stocks_used_column(apps, schema_editor):
    worksheet_model = apps.get_model('management', 'Worksheet')
    table_name = worksheet_model._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    if 'stocks_used' in columns:
        return

    field = models.PositiveIntegerField(default=1)
    field.set_attributes_from_name('stocks_used')
    schema_editor.add_field(worksheet_model, field)


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0090_employee_token_naming_access'),
    ]

    operations = [
        migrations.RunPython(ensure_stocks_used_column, migrations.RunPython.noop),
    ]
