from django.contrib import admin

from .models import Issue, Order, OrderEvent


class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 0
    fields = ("kind", "text", "created")
    readonly_fields = ("created",)
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "user_phone",
        "status",
        "total",
        "delivery_date",
        "delivery_time",
        "rush_mark",
        "utm_source",
    )
    list_filter = ("status", "is_rush", "is_rescheduled", "delivery_date", "utm_source")
    search_fields = (
        "number",
        "user__phone",
        "user__name",
        "address",
        "comment",
        "courier_comment",
    )
    date_hierarchy = "delivery_date"
    ordering = ("delivery_date", "delivery_time")
    readonly_fields = ("number", "created", "subtotal", "rush_amount", "is_rush")
    inlines = [OrderEventInline]
    fieldsets = (
        (
            "Заказ",
            {
                "fields": (
                    "number",
                    "user",
                    "status",
                    "total",
                    "discount",
                    "promo",
                    "created",
                )
            },
        ),
        (
            "Что готовить",
            {"fields": ("spec", "price_items", "subtotal", "is_rush", "rush_amount")},
        ),
        (
            "Куда везти",
            {
                "fields": (
                    "address",
                    "delivery_date",
                    "delivery_time",
                    "is_rescheduled",
                    "reschedule_note",
                )
            },
        ),
        ("Пожелания", {"fields": ("comment", "courier_comment")}),
        (
            "Согласие на ПД",
            {"fields": ("pd_consent_at", "pd_consent_ip", "pd_version")},
        ),
        (
            "Откуда пришёл",
            {
                "fields": (
                    "utm_source",
                    "utm_medium",
                    "utm_campaign",
                    "utm_content",
                    "utm_term",
                    "referrer",
                    "session_key",
                )
            },
        ),
    )

    @admin.display(description="телефон", ordering="user__phone")
    def user_phone(self, obj):
        return obj.user.phone

    @admin.display(description="срочный", boolean=True, ordering="is_rush")
    def rush_mark(self, obj):
        return obj.is_rush


@admin.register(OrderEvent)
class OrderEventAdmin(admin.ModelAdmin):
    list_display = ("order", "kind", "text", "created")
    list_filter = ("kind",)
    search_fields = ("order__number", "text")
    raw_id_fields = ("order",)
    date_hierarchy = "created"


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ("order", "message", "resolved", "created")
    list_editable = ("resolved",)
    list_filter = ("resolved",)
    search_fields = ("order__number", "message")
    raw_id_fields = ("order",)
    date_hierarchy = "created"
