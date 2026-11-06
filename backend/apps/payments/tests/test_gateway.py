import pytest

from apps.orders.models import Order, OrderEvent
from apps.payments.gateway import InMemoryGateway, PaymentError, handle_webhook, start_payment
from apps.payments.models import Payment
from apps.users.models import User


def _order(status=Order.Status.NEW, total=1500):
    user = User.objects.create(phone=f"+7900000{User.objects.count():04d}")
    return Order.objects.create(
        user=user,
        status=status,
        total=total,
        delivery_date="2026-11-10",
        delivery_time="12:00:00",
    )


@pytest.mark.django_db
def test_start_payment_creates_charge_and_reuses_pending():
    order = _order()
    gateway = InMemoryGateway()

    payment = start_payment(order, return_url="https://site.test/return", gateway=gateway)
    again = start_payment(order, return_url="https://site.test/return", gateway=gateway)

    assert payment.pk == again.pk
    assert payment.provider_id == f"test_pay_{payment.pk}"
    assert payment.confirmation_url
    assert len(gateway.charges) == 1
    assert Payment.objects.count() == 1


@pytest.mark.django_db
def test_start_payment_rejects_paid_order():
    order = _order(status=Order.Status.PAID)

    with pytest.raises(PaymentError) as exc:
        start_payment(order, return_url="x", gateway=InMemoryGateway())

    assert exc.value.errors == {"order": "Заказ уже оплачен или закрыт"}
    assert exc.value.status == 409


@pytest.mark.django_db
def test_start_payment_rejects_unconfigured_gateway():
    order = _order()
    gateway = InMemoryGateway()
    gateway.configured = False

    with pytest.raises(PaymentError) as exc:
        start_payment(order, return_url="x", gateway=gateway)

    assert exc.value.errors == {"pay": "Оплата временно недоступна, попробуйте позже"}
    assert exc.value.status == 503


@pytest.mark.django_db
def test_handle_webhook_marks_paid_idempotently():
    order = _order()
    Payment.objects.create(order=order, amount=1500, provider_id="gw_1")

    first = handle_webhook({"object": {"id": "gw_1", "status": "succeeded"}})
    second = handle_webhook({"object": {"id": "gw_1", "status": "succeeded"}})

    assert first is not None
    assert second is not None
    assert OrderEvent.objects.filter(order=order, kind=OrderEvent.Kind.PAID).count() == 1


@pytest.mark.django_db
def test_handle_webhook_returns_none_for_unknown_or_ignored():
    assert handle_webhook({"object": {"id": "nope", "status": "succeeded"}}) is None
    assert handle_webhook({"object": {"id": "x", "status": "pending"}}) is None
    assert handle_webhook({}) is None
