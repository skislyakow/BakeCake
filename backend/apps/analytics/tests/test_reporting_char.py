from datetime import date, datetime
from datetime import timezone as dt_timezone

import pytest

from apps.analytics.models import Visit
from apps.analytics.reporting import build_stats
from apps.analytics.templatetags.links import campaign_link_rows
from apps.orders.models import Order
from apps.users.models import User


def _user(n=1):
    return User.objects.create(phone=f"+790099900{n:02d}")


def _order(user, *, status=Order.Status.NEW, total=1000, utm_source="", utm_campaign="", created_on=date(2026, 5, 10)):
    order = Order.objects.create(
        user=user,
        status=status,
        total=total,
        utm_source=utm_source,
        utm_campaign=utm_campaign,
        delivery_date="2026-05-20",
        delivery_time="12:00:00",
    )
    Order.objects.filter(pk=order.pk).update(created=datetime(created_on.year, created_on.month, created_on.day, 9, 0, tzinfo=dt_timezone.utc))
    return order


def _visit(*, utm_source="", utm_campaign="", created_on=date(2026, 5, 10)):
    visit = Visit.objects.create(session_key=f"s{Visit.objects.count()}", utm_source=utm_source, utm_campaign=utm_campaign, landing_path="/")
    Visit.objects.filter(pk=visit.pk).update(created=datetime(created_on.year, created_on.month, created_on.day, 9, 0, tzinfo=dt_timezone.utc))
    return visit


@pytest.mark.django_db
def test_build_stats_counts_paid_revenue_only():
    user = _user()
    _order(user, status=Order.Status.PAID, total=1000, utm_source="ig")
    _order(user, status=Order.Status.DELIVERED, total=500, utm_source="ig")
    _order(user, status=Order.Status.NEW, total=9999, utm_source="ig")
    _visit(utm_source="ig")
    _visit(utm_source="ig")

    data = build_stats(date(2026, 5, 1), date(2026, 5, 31))

    assert data["orders"] == 3
    assert data["paid"] == 2
    assert data["revenue"] == 1500
    assert data["avg_check"] == 750
    assert data["visits"] == 2
    assert data["conversion"] == 100.0
    assert data["channels"] == [
        {"source": "ig", "visits": 2, "orders": 3, "paid": 2, "revenue": 1500, "avg_check": 750, "conversion": 100.0}
    ]


@pytest.mark.django_db
def test_build_stats_labels_direct_and_filters():
    user = _user()
    _order(user, status=Order.Status.PAID, total=100, utm_source="")
    _order(user, status=Order.Status.PAID, total=200, utm_source="vk", created_on=date(2026, 4, 1))
    _visit(utm_source="")

    data = build_stats(date(2026, 5, 1), date(2026, 5, 31))

    assert data["revenue"] == 100
    assert data["channels"][0]["source"] == "прямой"


@pytest.mark.django_db
def test_campaign_link_rows_uses_paid_revenue_definition():
    user = _user()
    _order(user, status=Order.Status.PAID, total=1000, utm_source="ig", utm_campaign="spring")
    _order(user, status=Order.Status.NEW, total=9999, utm_source="ig", utm_campaign="spring")
    _visit(utm_source="ig", utm_campaign="spring")

    rows = campaign_link_rows()

    assert rows == [{"source": "ig", "campaign": "spring", "visits": 1, "orders": 2, "revenue": 1000}]
