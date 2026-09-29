from django.contrib import admin
from .models import Option, OptionGroup


class OptionInline(admin.TabularInline):
    model = Option
    extra = 1
    fields = ("title", "price_delta", "is_available", "sort")


@admin.register(OptionGroup)
class OptionGroupAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "is_required", "sort", "options_count")
    list_editable = ("is_required", "sort")
    list_filter = ("is_required",)
    search_fields = ("title", "code")
    ordering = ("sort", "id")
    inlines = [OptionInline]

    @admin.display(description="опций")
    def options_count(self, obj):
        return obj.options.count()


@admin.register(Option)
class OptionAdmin(admin.ModelAdmin):
    list_display = ("title", "group", "price_delta", "is_available", "sort")
    list_editable = ("price_delta", "is_available", "sort")
    list_filter = ("group", "is_available")
    search_fields = ("title",)
    ordering = ("group__sort", "sort", "id")
