from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('pricing', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='option',
            name='preview_key',
            field=models.SlugField(blank=True, default='', help_text='Как опция выглядит в предпросмотре торта, например level_2 или form_circle.', max_length=40, verbose_name='ключ превью'),
        ),
    ]
