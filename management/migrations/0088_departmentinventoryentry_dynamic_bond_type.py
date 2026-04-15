from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0087_token_customer_name_column_fix'),
    ]

    operations = [
        migrations.AlterField(
            model_name='departmentinventoryentry',
            name='bond_type',
            field=models.CharField(max_length=200),
        ),
    ]
