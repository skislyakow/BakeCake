from django.conf import settings
from django.db import models


class Visit(models.Model):
    session_key = models.CharField("сессия", max_length=60, db_index=True)
    utm_source = models.CharField("источник", max_length=100, blank=True, db_index=True)
    utm_medium = models.CharField("medium", max_length=100, blank=True)
    utm_campaign = models.CharField("кампания", max_length=100, blank=True)
    utm_content = models.CharField("content", max_length=100, blank=True)
    utm_term = models.CharField("term", max_length=100, blank=True)
    referrer = models.CharField("источник перехода", max_length=500, blank=True)
    landing_path = models.CharField("страница входа", max_length=300, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="visits",
        verbose_name="пользователь",
    )
    created = models.DateTimeField("создан", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "визит"
        verbose_name_plural = "визиты"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.utm_source or 'прямой'} — {self.landing_path}"
