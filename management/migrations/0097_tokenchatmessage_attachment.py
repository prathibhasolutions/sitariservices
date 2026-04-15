from django.db import migrations, models
import management.models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0096_tokenchatmessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='tokenchatmessage',
            name='attachment',
            field=models.FileField(blank=True, null=True, upload_to=management.models.token_chat_attachment_upload_to),
        ),
    ]
