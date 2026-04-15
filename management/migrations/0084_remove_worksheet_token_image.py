from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0083_ttd_models'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='worksheet',
            name='token_image',
        ),
    ]