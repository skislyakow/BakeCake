from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order_number", "provider", "amount", "status", "created")
    list_filter = ("provider", "status")
    search_fields = ("order__number", "provider_id", "idempotency_key")
    raw_id_fields = ("order",)
    date_hierarchy = "created"

    @admin.display(description="заказ", ordering="order__number")
    def order_number(self, obj):
        return f"#{obj.order.number}"
