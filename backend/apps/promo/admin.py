from django.contrib import admin
from .models import PromoCode


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "percent", "active")
    list_editable = ("percent", "active")
    list_filter = ("active",)
    search_fields = ("code",)
