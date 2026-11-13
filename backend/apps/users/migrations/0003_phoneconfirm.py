import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0002_normalize_phone'),
    ]

    operations = [
        migrations.CreateModel(
            name='PhoneConfirm',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name='токен')),
                ('phone', models.CharField(db_index=True, max_length=20, verbose_name='телефон')),
                ('status', models.CharField(choices=[('pending', 'ожидает'), ('confirmed', 'подтверждён'), ('rejected', 'отклонён'), ('expired', 'истёк')], default='pending', max_length=16, verbose_name='статус')),
                ('attempts', models.PositiveSmallIntegerField(default=0, verbose_name='попыток')),
                ('expires_at', models.DateTimeField(verbose_name='истекает')),
                ('zvonok_id', models.CharField(blank=True, max_length=100, verbose_name='ID проверки у провайдера')),
                ('session_issued', models.BooleanField(default=False, verbose_name='сессия открыта')),
                ('created', models.DateTimeField(auto_now_add=True, verbose_name='создано')),
                ('updated', models.DateTimeField(auto_now=True, verbose_name='обновлено')),
            ],
            options={
                'verbose_name': 'подтверждение номера',
                'verbose_name_plural': 'подтверждения номеров',
                'ordering': ['-created'],
                'indexes': [models.Index(fields=['phone', 'status', 'expires_at'], name='users_phone_phone_ee41b8_idx')],
            },
        ),
    ]
