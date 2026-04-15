from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0100_adminactivesession'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='worksheet_hidden',
            field=models.BooleanField(default=False, help_text="If enabled, this employee's worksheet entries are hidden from admin and employee worksheet screens."),
        ),
    ]
