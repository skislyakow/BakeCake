from datetime import date, time

import pytest

from apps.orders.lifecycle import mark_delivered, record_reschedule
from apps.orders.models import Order, OrderEvent
from apps.users.models import User


def _order(status=Order.Status.PAID):
    user = User.objects.create(phone=f"+7900000{User.objects.count():04d}")
    return Order.objects.create(
        user=user,
        status=status,
        total=1500,
        delivery_date=date(2026, 11, 10),
        delivery_time=time(12, 0),
    )


@pytest.mark.django_db
def test_mark_delivered_transitions_paid_to_delivered():
    order = _order()

    assert mark_delivered(order) is True

    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED
    assert OrderEvent.objects.filter(
        order=order, kind=OrderEvent.Kind.STATUS, text="Заказ выполнен"
    ).exists()


@pytest.mark.django_db
def test_mark_delivered_is_idempotent():
    order = _order(status=Order.Status.DELIVERED)

    assert mark_delivered(order) is False
    assert OrderEvent.objects.filter(order=order).count() == 0


@pytest.mark.django_db
def test_mark_delivered_rejects_unpaid_order():
    order = _order(status=Order.Status.NEW)

    with pytest.raises(ValueError):
        mark_delivered(order)

    order.refresh_from_db()
    assert order.status == Order.Status.NEW


@pytest.mark.django_db
def test_record_reschedule_sets_flags_and_keeps_status():
    order = _order()
    old_date, old_time = order.delivery_date, order.delivery_time
    order.delivery_date = date(2026, 11, 12)
    order.delivery_time = time(15, 30)
    order.save(update_fields=["delivery_date", "delivery_time"])

    assert record_reschedule(order, old_date, old_time) is True

    order.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.is_rescheduled is True
    assert order.reschedule_note == "Новые сроки: 12.11.2026 15:30"
    assert OrderEvent.objects.filter(
        order=order, kind=OrderEvent.Kind.RESCHEDULED
    ).exists()


@pytest.mark.django_db
def test_record_reschedule_keeps_existing_note():
    order = _order()
    order.reschedule_note = "Клиент просил перенести"
    order.save(update_fields=["reschedule_note"])
    old_date, old_time = order.delivery_date, order.delivery_time
    order.delivery_date = date(2026, 11, 13)
    order.save(update_fields=["delivery_date"])

    assert record_reschedule(order, old_date, old_time) is True

    order.refresh_from_db()
    assert order.reschedule_note == "Клиент просил перенести"


@pytest.mark.django_db
def test_record_reschedule_ignores_unchanged_slot():
    order = _order()

    assert record_reschedule(order, order.delivery_date, order.delivery_time) is False

    order.refresh_from_db()
    assert order.is_rescheduled is False
    assert OrderEvent.objects.filter(
        order=order, kind=OrderEvent.Kind.RESCHEDULED
    ).count() == 0
