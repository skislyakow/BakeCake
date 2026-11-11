from django.db import models


class OptionGroup(models.Model):
    code = models.SlugField("код", max_length=32, unique=True)
    title = models.CharField("название", max_length=100)
    is_required = models.BooleanField("обязательная", default=False)
    sort = models.PositiveSmallIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "группа опций"
        verbose_name_plural = "группы опций"
        ordering = ["sort", "id"]

    def __str__(self):
        return self.title


class Option(models.Model):
    group = models.ForeignKey(
        OptionGroup,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name="группа",
    )
    title = models.CharField("название", max_length=100)
    price_delta = models.IntegerField("доплата, ₽", default=0)
    preview_key = models.SlugField(
        "ключ превью",
        max_length=40,
        blank=True,
        default="",
        help_text="Как опция выглядит в предпросмотре торта, например level_2 или form_circle.",
    )
    is_available = models.BooleanField("доступна", default=True)
    sort = models.PositiveSmallIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "опция"
        verbose_name_plural = "опции"
        ordering = ["sort", "id"]

    def __str__(self):
        return f"{self.title} (+{self.price_delta} ₽)"
