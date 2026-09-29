from django.db import models


class Payment(models.Model):
    class Provider(models.TextChoices):
        YOOKASSA = "yookassa", "ЮKassa"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SUCCEEDED = "succeeded", "Успешно"
        CANCELED = "canceled", "Отменён"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="заказ",
    )
    provider = models.CharField(
        "провайдер", max_length=20, choices=Provider.choices, default=Provider.YOOKASSA
    )
    provider_id = models.CharField(
        "ID у провайдера", max_length=100, blank=True, unique=True, null=True
    )
    amount = models.IntegerField("сумма, ₽", default=0)
    status = models.CharField(
        "статус",
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    confirmation_url = models.URLField("ссылка на оплату", max_length=500, blank=True)
    idempotency_key = models.CharField(
        "ключ идемпотентности", max_length=100, blank=True, db_index=True
    )
    raw = models.JSONField("ответ провайдера", default=dict, blank=True)
    created = models.DateTimeField("создан", auto_now_add=True)

    class Meta:
        verbose_name = "платёж"
        verbose_name_plural = "платежи"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.get_provider_display()} {self.amount} ₽ — {self.get_status_display()}"  # pyright: ignore[reportAttributeAccessIssue]
