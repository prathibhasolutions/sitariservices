from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0092_chatbotservicetemplate'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatbotQuickOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=80, unique=True)),
                ('prompt_text', models.CharField(help_text='Text sent to chatbot when option is clicked.', max_length=200)),
                ('sort_order', models.PositiveIntegerField(default=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['sort_order', 'label'],
            },
        ),
    ]
