from django.db import models


class Cake(models.Model):
    name = models.CharField("название", max_length=150)
    slug = models.SlugField("адрес", max_length=150, unique=True)
    price = models.IntegerField("цена от, ₽", default=0)
    image = models.CharField("картинка", max_length=300, blank=True)
    description = models.TextField("описание", blank=True)
    occasion = models.CharField("повод", max_length=100, db_index=True)
    is_active = models.BooleanField("в каталоге", default=True)
    sort = models.PositiveSmallIntegerField("порядок", default=0)

    class Meta:
        verbose_name = "торт"
        verbose_name_plural = "торты"
        ordering = ["occasion", "sort", "id"]

    def __str__(self):
        return self.name
