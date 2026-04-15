from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0094_chatbotquickoption_followup_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatbotNumericTrigger',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trigger_number', models.CharField(help_text='Exact numeric trigger. Example: 101', max_length=20, unique=True)),
                ('response_text', models.TextField(help_text='Response sent when trigger number is matched exactly.')),
                ('response_pdf', models.FileField(blank=True, help_text='Optional PDF returned along with the response text.', null=True, upload_to='chatbot_trigger_pdfs/')),
                ('sort_order', models.PositiveIntegerField(default=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['sort_order', 'trigger_number'],
            },
        ),
    ]
