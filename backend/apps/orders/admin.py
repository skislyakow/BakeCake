import html

from django.contrib import admin
from django.utils.html import mark_safe

from apps.pricing.models import Option, OptionGroup

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
    readonly_fields = ("number", "created", "subtotal", "rush_amount", "is_rush", "spec_display")
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
            {"fields": ("spec_display", "subtotal", "is_rush", "rush_amount")},
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

    @admin.display(description="состав заказа")
    def spec_display(self, obj):
        spec = obj.spec or {}
        items = {
            item.get("title"): item.get("price") or 0
            for item in obj.price_items
            if isinstance(item, dict) and item.get("title")
        }
        groups = {g.code: g for g in OptionGroup.objects.all()}
        labels = {
            "levels": "Количество уровней",
            "form": "Форма торта",
            "topping": "Топпинг",
            "extra": "Дополнительно",
            "inscription": "Надпись",
        }
        used = set()

        def option_title(group, option_id):
            option = None
            if group:
                option = Option.objects.filter(id=option_id, group=group).first()
                if option is None:
                    option = next(
                        (
                            candidate
                            for candidate in group.options.all()
                            if candidate.title in items and candidate.title not in used
                        ),
                        None,
                    )
            if option is None:
                return f"#{option_id}"
            used.add(option.title)
            return option.title

        lines = []
        for code in ("levels", "form", "topping"):
            value = spec.get(code)
            if not value:
                continue
            group = groups.get(code)
            title = option_title(group, value)
            lines.append(f"{labels[code]}: {title} — {items.get(title, 0)} ₽")

        extras = []
        for code in ("berries", "decor"):
            value = spec.get(code)
            if not value:
                continue
            group = groups.get(code)
            title = option_title(group, value)
            extras.append(f"{group.title}: {title} — {items.get(title, 0)} ₽")
        if extras:
            lines.append(labels["extra"])
            lines.extend(f"    {line}" for line in extras)

        inscription = spec.get("inscription")
        if inscription:
            lines.append(f"{labels['inscription']}: {inscription} — {items.get('Надпись', 0)} ₽")

        if not lines:
            return mark_safe("—")
        return mark_safe("<br>".join(html.escape(line) for line in lines))

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
