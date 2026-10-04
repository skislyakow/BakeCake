from datetime import timedelta

from django import template
from django.db.models import Q, Sum
from django.utils import timezone

from apps.analytics.stats import build_stats
from apps.orders.models import Issue, Order

register = template.Library()

PAID_STATUSES = [Order.Status.PAID, Order.Status.DELIVERED]


@register.simple_tag
def dashboard_summary():
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)
    month_start = today.replace(day=1)

    status_counts = []
    for key, label in Order.Status.choices:
        status_counts.append(
            {
                "value": key,
                "label": label,
                "count": Order.objects.filter(status=key).count(),
            }
        )

    today_qs = Order.objects.filter(delivery_date=today)
    tomorrow_qs = Order.objects.filter(delivery_date=tomorrow)

    paid_revenue_qs = Q(status__in=PAID_STATUSES)
    revenue_today = today_qs.filter(paid_revenue_qs).aggregate(total=Sum("total"))["total"] or 0
    revenue_tomorrow = (
        tomorrow_qs.filter(paid_revenue_qs).aggregate(total=Sum("total"))["total"] or 0
    )

    recent_orders = Order.objects.select_related("user").order_by("-created")[:10]

    stats = build_stats(month_start, today)

    return {
        "status_counts": status_counts,
        "today_count": today_qs.count(),
        "today_revenue": revenue_today,
        "tomorrow_count": tomorrow_qs.count(),
        "tomorrow_revenue": revenue_tomorrow,
        "recent_orders": recent_orders,
        "open_issues": Issue.objects.filter(resolved=False).count(),
        "metrics": {
            "orders": stats["orders"],
            "revenue": stats["revenue"],
            "avg_check": stats["avg_check"],
            "conversion": stats["conversion"],
        },
        "channels": stats["channels"],
        "days": stats["days"],
        "csv_from": month_start.isoformat(),
        "csv_to": today.isoformat(),
    }