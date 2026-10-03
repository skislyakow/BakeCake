from django import template
from django.db.models import Count, Sum

from apps.analytics.models import Visit
from apps.orders.models import Order

register = template.Library()


@register.simple_tag
def campaign_link_rows():
    visits = {
        (row["utm_source"], row["utm_campaign"]): row["visits"]
        for row in Visit.objects.exclude(utm_source="")
        .values("utm_source", "utm_campaign")
        .annotate(visits=Count("id"))
    }
    orders = {
        (row["utm_source"], row["utm_campaign"]): row
        for row in Order.objects.exclude(utm_source="")
        .values("utm_source", "utm_campaign")
        .annotate(orders=Count("id"), revenue=Sum("total"))
    }
    keys = sorted(set(visits) | set(orders), key=lambda pair: (pair[0], pair[1]))
    rows = []
    for key in keys:
        group = orders.get(key, {})
        rows.append(
            {
                "source": key[0],
                "campaign": key[1],
                "visits": visits.get(key, 0),
                "orders": group.get("orders") or 0,
                "revenue": group.get("revenue") or 0,
            }
        )
    rows.sort(key=lambda row: row["revenue"], reverse=True)
    return rows