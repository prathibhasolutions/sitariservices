from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0089_token_no_yymmdd_sequence'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='token_naming_access',
            field=models.BooleanField(
                default=False,
                help_text='If enabled, employee can use Token Naming section from employee dashboard.',
            ),
        ),
    ]
