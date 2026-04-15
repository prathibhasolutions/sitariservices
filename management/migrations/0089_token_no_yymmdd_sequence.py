from django.db import migrations, models
import management.models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0088_departmentinventoryentry_dynamic_bond_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='token',
            name='token_no',
            field=models.CharField(
                default=management.models.generate_token_no,
                help_text='9-digit token number in yymmddNNN format',
                max_length=9,
                unique=True,
            ),
        ),
    ]
