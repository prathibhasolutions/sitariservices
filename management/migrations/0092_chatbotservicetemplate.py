from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0091_ensure_worksheet_stocks_used_column'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatbotServiceTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('service_name', models.CharField(max_length=120, unique=True)),
                ('keywords', models.CharField(blank=True, help_text='Comma-separated keywords used to match user queries.', max_length=255)),
                ('template_text', models.TextField(help_text='Static response shown by chatbot for this service.')),
                ('sort_order', models.PositiveIntegerField(default=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['sort_order', 'service_name'],
            },
        ),
    ]
