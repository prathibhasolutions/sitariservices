from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('management', '0097_tokenchatmessage_attachment'),
    ]

    operations = [
        migrations.CreateModel(
            name='TokenChatReadStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_opened_at', models.DateTimeField(blank=True, null=True)),
                ('last_seen_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='token_chat_read_statuses', to='management.employee')),
                ('token', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='read_statuses', to='management.token')),
            ],
            options={
                'verbose_name': 'Token Chat Read Status',
                'verbose_name_plural': 'Token Chat Read Statuses',
                'ordering': ['-updated_at'],
                'unique_together': {('token', 'employee')},
            },
        ),
    ]
