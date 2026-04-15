# Generated migration to replace boolean worksheet_entry_force_unlock with datetime field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0072_employeenextdayavailability'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='employee',
            name='worksheet_entry_force_unlock',
        ),
        migrations.AddField(
            model_name='employee',
            name='worksheet_entry_force_unlock_until',
            field=models.DateTimeField(blank=True, help_text='If set, this employee can add worksheet entries until this datetime. Null means no override active.', null=True),
        ),
    ]
