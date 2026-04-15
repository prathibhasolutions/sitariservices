from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0098_tokenchatreadstatus'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='token_entry_access',
            field=models.BooleanField(default=False, help_text='If enabled, employee can use Token+ entry option on worksheet page.'),
        ),
    ]
