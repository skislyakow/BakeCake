import html

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.utils.safestring import mark_safe

from apps.payments.gateway import mark_order_paid

from .composition import describe
from .lifecycle import mark_delivered, record_reschedule
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
    readonly_fields = ("number", "status", "created", "subtotal", "rush_amount", "is_rush", "spec_display")
    inlines = [OrderEventInline]
    actions = ("mark_paid_action", "mark_delivered_action")
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
        lines = describe(obj).admin_lines
        if not lines:
            return mark_safe("—")
        return mark_safe("<br>".join(html.escape(line.render()) for line in lines))

    @admin.display(description="телефон", ordering="user__phone")
    def user_phone(self, obj):
        return obj.user.phone

    @admin.display(description="срочный", boolean=True, ordering="is_rush")
    def rush_mark(self, obj):
        return obj.is_rush

    @admin.action(description="Отметить оплаченным (резерв при потерянном вебхуке)")
    def mark_paid_action(self, request, queryset):
        changed = sum(1 for order in queryset if mark_order_paid(order, manual=True))
        self.message_user(request, f"Отмечено оплаченным: {changed}", messages.SUCCESS)

    @admin.action(description="Отметить выполненным (только оплаченные)")
    def mark_delivered_action(self, request, queryset):
        changed = 0
        skipped = 0
        for order in queryset:
            if order.status != Order.Status.PAID:
                skipped += 1
                continue
            if mark_delivered(order):
                changed += 1
        self.message_user(request, f"Отмечено выполненным: {changed}", messages.SUCCESS)
        if skipped:
            self.message_user(
                request,
                f"Пропущено (не оплачены): {skipped}",
                messages.WARNING,
            )

    def save_model(self, request, obj, form, change):
        if change:
            old = Order.objects.get(pk=obj.pk)
            record_reschedule(obj, old.delivery_date, old.delivery_time)
        super().save_model(request, obj, form, change)

    def response_change(self, request, obj):
        if "_mark_paid" in request.POST:
            if mark_order_paid(obj, manual=True):
                self.message_user(request, "Заказ отмечен оплаченным", messages.SUCCESS)
            else:
                self.message_user(request, "Заказ уже оплачен или выполнен", messages.WARNING)
            return HttpResponseRedirect(request.path)
        if "_mark_delivered" in request.POST:
            if obj.status != Order.Status.PAID:
                self.message_user(
                    request,
                    "Выполненным можно отметить только оплаченный заказ",
                    messages.ERROR,
                )
            else:
                mark_delivered(obj)
                self.message_user(request, "Заказ отмечен выполненным", messages.SUCCESS)
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)


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
