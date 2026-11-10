"""Жизненный цикл оплаты за seam'ом провайдера.

Провайдер создаёт платёж у платёжной системы; состояние заказа и Payment
меняется здесь, одинаково для YooKassa и тестового адаптера.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

from django.db import transaction

from apps.orders.models import Order, OrderEvent

from .models import Payment

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    def __init__(self, errors: dict[str, str], status: int = 400):
        self.errors = errors
        self.status = status
        super().__init__(str(errors))


@dataclass(frozen=True)
class Charge:
    provider_id: str
    confirmation_url: str
    raw: dict[str, Any]


class PaymentGateway(Protocol):
    def is_configured(self) -> bool: ...

    def create_charge(self, *, order: Order, payment: Payment, return_url: str) -> Charge: ...


class YooKassaGateway:
    def is_configured(self) -> bool:
        from django.conf import settings

        return bool(settings.YOO_SHOP_ID and settings.YOO_SECRET_KEY)

    def _configure(self) -> None:
        from django.conf import settings
        from yookassa import Configuration

        Configuration.account_id = settings.YOO_SHOP_ID
        Configuration.secret_key = settings.YOO_SECRET_KEY

    def create_charge(self, *, order: Order, payment: Payment, return_url: str) -> Charge:
        from yookassa import Payment as YooPayment

        self._configure()
        yoo_payment = YooPayment.create(
            {
                "amount": {"value": f"{order.total:.2f}", "currency": "RUB"},
                "capture": True,
                "confirmation": {"type": "redirect", "return_url": return_url},
                "description": f"Торт на заказ #{order.number}",
                "metadata": {"order_id": order.pk, "order_number": order.number},
            }
        )
        confirmation = getattr(yoo_payment, "confirmation", None)
        confirmation_url = getattr(confirmation, "confirmation_url", None)
        if not confirmation_url:
            raise PaymentError({"pay": "Не удалось создать платёж, попробуйте позже"}, status=502)
        raw = yoo_payment if isinstance(yoo_payment, dict) else dict(yoo_payment)
        return Charge(provider_id=str(yoo_payment.id), confirmation_url=str(confirmation_url), raw=raw)


class InMemoryGateway:
    """Тестовый провайдер: не ходит в сеть, возвращает предсказуемую ссылку."""

    configured = True

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.charges: list[dict[str, Any]] = []

    def is_configured(self) -> bool:
        return self.configured

    def create_charge(self, *, order: Order, payment: Payment, return_url: str) -> Charge:
        if self.fail:
            raise PaymentError({"pay": "Не удалось создать платёж, попробуйте позже"}, status=502)
        provider_id = f"test_pay_{payment.pk}"
        confirmation_url = f"https://pay.test/confirm/{payment.pk}?return={order.number}"
        charge = Charge(provider_id=provider_id, confirmation_url=confirmation_url, raw={"id": provider_id})
        self.charges.append({"order": order.pk, "payment": payment.pk, "return_url": return_url, "charge": charge})
        return charge


def default_gateway() -> PaymentGateway:
    return YooKassaGateway()


def start_payment(order: Order, *, return_url: str, gateway: PaymentGateway | None = None) -> Payment:
    """Создаёт или переиспользует pending-платёж и возвращает его со ссылкой на оплату."""
    gateway = gateway or default_gateway()

    if order.status != Order.Status.NEW:
        raise PaymentError({"order": "Заказ уже оплачен или закрыт"}, status=409)

    if not gateway.is_configured():
        raise PaymentError({"pay": "Оплата временно недоступна, попробуйте позже"}, status=503)

    with transaction.atomic():
        payment = Payment.objects.filter(order=order, status=Payment.Status.PENDING).order_by("-created").first()
        if payment is None:
            payment = Payment.objects.create(order=order, amount=order.total)

        if payment.provider_id and payment.confirmation_url:
            return payment

        try:
            charge = gateway.create_charge(order=order, payment=payment, return_url=return_url)
        except PaymentError:
            raise
        except Exception:
            logger.exception("Ошибка создания платежа для заказа %s", order.pk)
            raise PaymentError({"pay": "Не удалось создать платёж, попробуйте позже"}, status=502) from None

        payment.provider_id = charge.provider_id
        payment.confirmation_url = charge.confirmation_url
        payment.raw = charge.raw
        payment.save()
        return payment


def mark_paid(payment: Payment, *, event_text: str = "Оплата получена") -> None:
    """Отмечает платёж и заказ оплаченными. Идемпотентно."""
    with transaction.atomic():
        payment = Payment.objects.select_related("order").get(pk=payment.pk)
        if payment.status != Payment.Status.SUCCEEDED:
            payment.status = Payment.Status.SUCCEEDED
            payment.save(update_fields=["status"])

        order = payment.order
        if order.status == Order.Status.NEW:
            order.status = Order.Status.PAID
            order.save(update_fields=["status"])
            OrderEvent.objects.create(order=order, kind=OrderEvent.Kind.PAID, text=event_text)


def mark_order_paid(order: Order, *, manual: bool = False) -> bool:
    """Резерв на случай потерянного вебхука: переводит `new → paid` вручную.

    Возвращает `False`, если заказ уже оплачен или выполнен: переход не
    откатывает статус назад.
    """
    event_text = "Оплата подтверждена вручную" if manual else "Оплата получена"
    with transaction.atomic():
        order = Order.objects.get(pk=order.pk)
        if order.status != Order.Status.NEW:
            return False

        payment = Payment.objects.filter(order=order).order_by("-created").first()
        if payment is not None:
            mark_paid(payment, event_text=event_text)
        else:
            order.status = Order.Status.PAID
            order.save(update_fields=["status"])
            OrderEvent.objects.create(order=order, kind=OrderEvent.Kind.PAID, text=event_text)
    return True


def handle_webhook(payload: dict[str, Any]) -> Payment | None:
    """Применяет уведомление провайдера. Возвращает найденный платёж, если он был."""
    obj = payload.get("object") if isinstance(payload, dict) else {}
    if not isinstance(obj, dict):
        return None
    payment_id = obj.get("id")
    status = obj.get("status")
    if status != "succeeded" or not payment_id:
        return None

    payment = Payment.objects.filter(provider_id=str(payment_id)).first()
    if payment is None:
        logger.warning("Платёж провайдера %s не найден в BakeCake", payment_id)
        return None
    mark_paid(payment)
    return payment
