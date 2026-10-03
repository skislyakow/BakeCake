from django.contrib import admin
from django.urls import path

from apps.analytics import views
from apps.analytics.models import Visit

_original_get_urls = admin.site.get_urls


def _get_urls():
    urls = _original_get_urls()
    urls = [path("summary/", admin.site.admin_view(views.summary), name="analytics-summary")] + urls
    return urls


admin.site.get_urls = _get_urls


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        "created",
        "utm_source",
        "utm_medium",
        "landing_path",
        "session_key",
    )
    list_filter = ("utm_source", "utm_medium")
    search_fields = ("utm_source", "utm_campaign", "landing_path", "session_key")
    date_hierarchy = "created"
    readonly_fields = [f.name for f in Visit._meta.fields]
