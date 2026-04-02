from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0093_chatbotquickoption'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatbotquickoption',
            name='followup_answer',
            field=models.TextField(blank=True, help_text='Auto reply shown when this option is selected. If empty, chatbot reply API is used.'),
        ),
        migrations.AddField(
            model_name='chatbotquickoption',
            name='followup_options',
            field=models.CharField(blank=True, help_text='Comma-separated option labels to show as next-step choices.', max_length=255),
        ),
    ]
