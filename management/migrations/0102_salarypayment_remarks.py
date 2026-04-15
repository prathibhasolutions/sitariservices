from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0101_employee_worksheet_hidden'),
    ]

    operations = [
        migrations.AddField(
            model_name='salarypayment',
            name='remarks',
            field=models.CharField(
                blank=True,
                default='',
                max_length=500,
                help_text='Optional remarks for this payment.',
            ),
        ),
    ]
