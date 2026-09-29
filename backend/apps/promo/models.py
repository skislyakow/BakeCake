from django.db import models


class PromoCode(models.Model):
    code = models.CharField("код", max_length=50, unique=True)
    percent = models.PositiveSmallIntegerField("скидка, %", default=10)
    active = models.BooleanField("активен", default=True)

    class Meta:
        verbose_name = "промокод"
        verbose_name_plural = "промокоды"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} (−{self.percent}%)"
