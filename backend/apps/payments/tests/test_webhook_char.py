import json

import pytest

from apps.orders.models import Order, OrderEvent
from apps.payments.models import Payment
from apps.users.models import User


def _order(status=Order.Status.NEW):
    user = User.objects.create(phone="+79000000001")
    return Order.objects.create(
        user=user,
        status=status,
        total=1500,
        delivery_date="2026-11-10",
        delivery_time="12:00:00",
    )


@pytest.mark.django_db
def test_webhook_marks_payment_and_order_paid(client):
    order = _order()
    payment = Payment.objects.create(order=order, amount=1500, provider_id="pay_1")

    resp = client.post(
        "/api/yookassa/webhook/",
        data=json.dumps({"object": {"id": "pay_1", "status": "succeeded"}}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    payment.refresh_from_db()
    order.refresh_from_db()
    assert payment.status == Payment.Status.SUCCEEDED
    assert order.status == Order.Status.PAID
    assert OrderEvent.objects.filter(order=order, kind=OrderEvent.Kind.PAID).count() == 1


@pytest.mark.django_db
def test_webhook_is_idempotent(client):
    order = _order()
    Payment.objects.create(order=order, amount=1500, provider_id="pay_2")
    payload = {"object": {"id": "pay_2", "status": "succeeded"}}

    client.post("/api/yookassa/webhook/", data=json.dumps(payload), content_type="application/json")
    client.post("/api/yookassa/webhook/", data=json.dumps(payload), content_type="application/json")

    assert Payment.objects.get(provider_id="pay_2").status == Payment.Status.SUCCEEDED
    assert Order.objects.get(pk=order.pk).status == Order.Status.PAID
    assert OrderEvent.objects.filter(order=order, kind=OrderEvent.Kind.PAID).count() == 1


@pytest.mark.django_db
def test_webhook_does_not_regress_delivered_order(client):
    order = _order(status=Order.Status.DELIVERED)
    Payment.objects.create(order=order, amount=1500, provider_id="pay_delivered")

    resp = client.post(
        "/api/yookassa/webhook/",
        data=json.dumps({"object": {"id": "pay_delivered", "status": "succeeded"}}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED
    assert OrderEvent.objects.filter(order=order, kind=OrderEvent.Kind.PAID).count() == 0


@pytest.mark.django_db
def test_webhook_ignores_unknown_payment(client):
    resp = client.post(
        "/api/yookassa/webhook/",
        data=json.dumps({"object": {"id": "missing", "status": "succeeded"}}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.django_db
def test_webhook_ignores_non_success_status(client):
    order = _order()
    Payment.objects.create(order=order, amount=1500, provider_id="pay_3")

    resp = client.post(
        "/api/yookassa/webhook/",
        data=json.dumps({"object": {"id": "pay_3", "status": "pending"}}),
        content_type="application/json",
    )

    assert resp.status_code == 200
    assert Payment.objects.get(provider_id="pay_3").status == Payment.Status.PENDING
    assert Order.objects.get(pk=order.pk).status == Order.Status.NEW
