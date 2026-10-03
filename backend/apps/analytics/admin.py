from django.contrib import admin

from apps.analytics.models import Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    change_list_template = "admin/analytics/visit/change_list.html"

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
