import random

from django.conf import settings
from django.db import models


def generate_number():
    return str(random.randint(10**9, 10**10 - 1))


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        PAID = "paid", "Оплачен"
        DELIVERED = "delivered", "Выполнен"

    number = models.CharField("номер", max_length=20, unique=True, default=generate_number)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="покупатель",
    )
    status = models.CharField(
        "статус", max_length=16, choices=Status.choices, default=Status.NEW, db_index=True
    )

    spec = models.JSONField("спецификация", default=dict, blank=True)
    price_items = models.JSONField("разбивка по позициям", default=list, blank=True)
    subtotal = models.IntegerField("сумма торта", default=0)
    total = models.IntegerField("итого", default=0)
    discount = models.IntegerField("скидка", default=0)
    promo = models.ForeignKey(
        "promo.PromoCode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="промокод",
    )

    delivery_date = models.DateField("дата доставки", db_index=True)
    delivery_time = models.TimeField("время доставки")

    is_rush = models.BooleanField("срочный", default=False)
    rush_amount = models.IntegerField("надбавка за срочность", default=0)

    address = models.CharField("адрес доставки", max_length=300, blank=True)
    comment = models.TextField("комментарий к заказу", blank=True)
    courier_comment = models.TextField("комментарий для курьера", blank=True)

    pd_consent_at = models.DateTimeField("согласие на ПД", null=True, blank=True)
    pd_consent_ip = models.GenericIPAddressField("IP согласия", null=True, blank=True)
    pd_version = models.CharField("версия согласия", max_length=20, blank=True)

    utm_source = models.CharField("источник", max_length=100, blank=True, db_index=True)
    utm_medium = models.CharField("medium", max_length=100, blank=True)
    utm_campaign = models.CharField("кампания", max_length=100, blank=True)
    utm_content = models.CharField("content", max_length=100, blank=True)
    utm_term = models.CharField("term", max_length=100, blank=True)
    referrer = models.CharField("источник перехода", max_length=500, blank=True)
    session_key = models.CharField("сессия", max_length=60, blank=True, db_index=True)

    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="платёж",
    )

    is_rescheduled = models.BooleanField("перенесён", default=False)
    reschedule_note = models.CharField("причина переноса", max_length=300, blank=True)

    created = models.DateTimeField("создан", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "заказ"
        verbose_name_plural = "заказы"
        ordering = ["delivery_date", "delivery_time"]

    def __str__(self):
        return f"#{self.number} — {self.get_status_display()}"  # pyright: ignore[reportAttributeAccessIssue]


class OrderEvent(models.Model):
    class Kind(models.TextChoices):
        STATUS = "status", "Статус изменён"
        RESCHEDULED = "rescheduled", "Новые сроки доставки"
        ISSUE = "issue", "Жалоба"
        PAID = "paid", "Оплата получена"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events", verbose_name="заказ")
    kind = models.CharField("тип", max_length=20, choices=Kind.choices, default=Kind.STATUS)
    text = models.CharField("текст", max_length=300, blank=True)
    created = models.DateTimeField("создано", auto_now_add=True)

    class Meta:
        verbose_name = "событие заказа"
        verbose_name_plural = "события заказа"
        ordering = ["created"]

    def __str__(self):
        return f"{self.order.number}: {self.get_kind_display()}"  # pyright: ignore[reportAttributeAccessIssue]


class Issue(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="issues", verbose_name="заказ")
    message = models.TextField("что случилось")
    resolved = models.BooleanField("решено", default=False)
    created = models.DateTimeField("создано", auto_now_add=True)

    class Meta:
        verbose_name = "жалоба"
        verbose_name_plural = "жалобы"
        ordering = ["-created"]

    def __str__(self):
        return f"Жалоба по заказу #{self.order.number}"
