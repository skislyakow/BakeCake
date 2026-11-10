"""Жизненный цикл заказа: переходы, которые делает админ, и их события."""

from datetime import date, time

from .models import Order, OrderEvent


def mark_delivered(order: Order) -> bool:
    """`paid → delivered`. Возвращает False, если заказ уже выполнен."""
    if order.status == Order.Status.DELIVERED:
        return False
    if order.status != Order.Status.PAID:
        raise ValueError("Выполненным можно отметить только оплаченный заказ")

    order.status = Order.Status.DELIVERED
    order.save(update_fields=["status"])
    OrderEvent.objects.create(order=order, kind=OrderEvent.Kind.STATUS, text="Заказ выполнен")
    return True


def record_reschedule(order: Order, old_date: date, old_time: time) -> bool:
    """Фиксирует перенос доставки админом, не меняя статус заказа."""
    if order.delivery_date == old_date and order.delivery_time == old_time:
        return False

    order.is_rescheduled = True
    if not order.reschedule_note:
        order.reschedule_note = (
            f"Новые сроки: {order.delivery_date:%d.%m.%Y} {order.delivery_time:%H:%M}"
        )
    order.save(update_fields=["is_rescheduled", "reschedule_note"])
    OrderEvent.objects.create(
        order=order,
        kind=OrderEvent.Kind.RESCHEDULED,
        text=order.reschedule_note,
    )
    return True
