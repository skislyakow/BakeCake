from django.contrib import admin
from .models import Cake


@admin.register(Cake)
class CakeAdmin(admin.ModelAdmin):
    list_display = ("name", "occasion", "price", "is_active", "sort", "image")
    list_editable = ("price", "is_active", "sort")
    list_filter = ("occasion", "is_active")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("occasion", "sort", "id")
