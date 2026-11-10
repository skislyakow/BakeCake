from datetime import date, time

import pytest
from django.contrib.auth import get_user_model

from apps.orders.models import Order


def _order(status):
    user = get_user_model().objects.create(phone=f"+7900000{Order.objects.count():04d}")
    return Order.objects.create(
        user=user,
        status=status,
        total=1500,
        delivery_date=date(2026, 11, 10),
        delivery_time=time(12, 0),
    )


def _admin_client(client):
    admin = get_user_model().objects.create_superuser(phone="+79000000099", password="admin")
    client.force_login(admin)
    return client


@pytest.mark.django_db
def test_admin_order_form_offers_mark_paid_for_new_order(client):
    _admin_client(client)
    order = _order(Order.Status.NEW)

    resp = client.get(f"/admin/orders/order/{order.pk}/change/")

    assert resp.status_code == 200
    assert "Отметить оплаченным" in resp.content.decode()


@pytest.mark.django_db
def test_admin_order_form_offers_mark_delivered_for_paid_order(client):
    _admin_client(client)
    order = _order(Order.Status.PAID)

    resp = client.get(f"/admin/orders/order/{order.pk}/change/")

    assert resp.status_code == 200
    assert "Отметить выполненным" in resp.content.decode()
