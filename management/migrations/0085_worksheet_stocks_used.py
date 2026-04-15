from django.db import migrations, models


class Migration(migrations.Migration):
    """
    The 'stocks_used' column was added directly via SQLite before this migration
    was created. We use SeparateDatabaseAndState so Django updates its internal
    state without running another ALTER TABLE (which would fail on the existing
    column).
    """

    dependencies = [
        ('management', '0084_remove_worksheet_token_image'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='worksheet',
                    name='stocks_used',
                    field=models.PositiveIntegerField(default=1),
                ),
            ],
            database_operations=[],
        ),
    ]
