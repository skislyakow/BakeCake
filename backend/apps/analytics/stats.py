from datetime import date, datetime, time
from typing import Optional

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate

from apps.analytics.models import Visit
from apps.orders.models import Order

PAID_STATUSES = [Order.Status.PAID, Order.Status.DELIVERED]
DIRECT_LABEL = "прямой"


def parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _created_range_qs(queryset, from_date, to_date):
    query = Q()
    if from_date:
        query &= Q(created__date__gte=from_date)
    if to_date:
        query &= Q(created__date__lte=to_date)
    return queryset.filter(query)


def build_stats(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    utm_source: Optional[str] = None,
):
    orders_qs = _created_range_qs(Order.objects.all(), from_date, to_date)
    visits_qs = _created_range_qs(Visit.objects.all(), from_date, to_date)
    if utm_source:
        orders_qs = orders_qs.filter(utm_source=utm_source)
        visits_qs = visits_qs.filter(utm_source=utm_source)

    paid_qs = orders_qs.filter(status__in=PAID_STATUSES)

    orders_total = orders_qs.count()
    paid_total = paid_qs.count()
    revenue_total = paid_qs.aggregate(total=Sum("total"))["total"] or 0
    visits_total = visits_qs.count()

    avg_check = round(revenue_total / paid_total) if paid_total else 0
    conversion = round(paid_total / visits_total * 100, 1) if visits_total else 0.0

    order_groups = {
        row["utm_source"]: row
        for row in orders_qs.values("utm_source").annotate(
            orders=Count("id"),
            paid=Count("id", filter=Q(status__in=PAID_STATUSES)),
            revenue=Sum("total", filter=Q(status__in=PAID_STATUSES)),
        )
    }
    visit_groups = {
        row["utm_source"]: row["visits"]
        for row in visits_qs.values("utm_source").annotate(visits=Count("id"))
    }

    channels = []
    for source in sorted(set(order_groups) | set(visit_groups)):
        visited = visit_groups.get(source, 0)
        group = order_groups.get(source, {"orders": 0, "paid": 0, "revenue": 0})
        paid = group["paid"] or 0
        revenue = group["revenue"] or 0
        channels.append(
            {
                "source": source or DIRECT_LABEL,
                "visits": visited,
                "orders": group["orders"] or 0,
                "paid": paid,
                "revenue": revenue,
                "avg_check": round(revenue / paid) if paid else 0,
                "conversion": round(paid / visited * 100, 1) if visited else 0.0,
            }
        )
    channels.sort(key=lambda row: (row["revenue"], row["orders"]), reverse=True)

    days_rows = (
        orders_qs.annotate(day=TruncDate("created"))
        .values("day")
        .annotate(
            orders=Count("id"),
            revenue=Sum("total", filter=Q(status__in=PAID_STATUSES)),
        )
        .order_by("day")
    )
    days = [
        {
            "date": row["day"].isoformat(),
            "orders": row["orders"],
            "revenue": row["revenue"] or 0,
        }
        for row in days_rows
    ]

    return {
        "orders": orders_total,
        "paid": paid_total,
        "revenue": revenue_total,
        "avg_check": avg_check,
        "conversion": conversion,
        "visits": visits_total,
        "channels": channels,
        "days": days,
    }


def format_hhmm(value: Optional[time]) -> str:
    return value.strftime("%H:%M") if value else ""