import json
import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from yookassa import Configuration, Payment as YooPayment

from apps.orders.models import Order, OrderEvent
from config.responses import fail, ok

from .models import Payment

logger = logging.getLogger(__name__)


def _configure_yookassa():
    if not settings.YOO_SHOP_ID or not settings.YOO_SECRET_KEY:
        return False
    Configuration.account_id = settings.YOO_SHOP_ID
    Configuration.secret_key = settings.YOO_SECRET_KEY
    return True


@api_view(["POST"])
def create_payment(request, order_id):
    """Создать платёж ЮKassa и вернуть ссылку на оплату (или повторный pending-платёж)."""
    if not request.user.is_authenticated:
        return fail({"auth": "Не авторизован"})

    order = request.user.orders.filter(pk=order_id).first()
    if order is None:
        return fail({"order": "Заказ не найден"})

    if order.status != Order.Status.NEW:
        return fail({"order": "Заказ уже оплачен или закрыт"})

    if not _configure_yookassa():
        return fail({"pay": "Оплата временно недоступна, попробуйте позже"})

    payment = order.payments.filter(status=Payment.Status.PENDING).order_by("-created").first()
    if payment is None:
        payment = Payment.objects.create(order=order, amount=order.total)

    if payment.provider_id and payment.confirmation_url:
        return ok(confirmation_url=payment.confirmation_url)

    try:
        yoo_payment = YooPayment.create(
            {
                "amount": {"value": f"{order.total:.2f}", "currency": "RUB"},
                "capture": True,
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"{settings.SITE_URL}/orders/?order={order.number}&paid=1",
                },
                "description": f"Торт на заказ #{order.number}",
                "metadata": {"order_id": order.pk, "order_number": order.number},
            }
        )
    except Exception:
        logger.exception("Ошибка создания платежа ЮKassa для заказа %s", order.pk)
        return fail({"pay": "Не удалось создать платёж, попробуйте позже"})

    confirmation = yoo_payment.confirmation
    if confirmation is None or not confirmation.confirmation_url:
        return fail({"pay": "Не удалось создать платёж, попробуйте позже"})

    payment.provider_id = yoo_payment.id
    payment.confirmation_url = confirmation.confirmation_url
    payment.raw = dict(yoo_payment)
    payment.save()

    return ok(confirmation_url=payment.confirmation_url)


def _mark_paid(payment):
    """Отметить платёж и заказ оплаченными. Идемпотентно."""
    if payment.status != Payment.Status.SUCCEEDED:
        payment.status = Payment.Status.SUCCEEDED
        payment.save(update_fields=["status"])

    order = payment.order
    if order.status != Order.Status.PAID:
        order.status = Order.Status.PAID
        order.save(update_fields=["status"])
        OrderEvent.objects.create(order=order, kind=OrderEvent.Kind.PAID, text="Оплата получена")


@csrf_exempt
def webhook(request):
    """Уведомление от ЮKassa о смене статуса платежа."""
    if request.method != "POST":
        return _json_response({"error": "POST required"}, status=400)
    try:
        data = json.loads(request.body)
        payment_id = data.get("object", {}).get("id")
        status = data.get("object", {}).get("status")
        if status == "succeeded" and payment_id:
            payment = Payment.objects.filter(provider_id=payment_id).first()
            if payment is not None:
                _mark_paid(payment)
            else:
                logger.warning("Платёж ЮKassa %s не найден в BakeCake", payment_id)
        return _json_response({"status": "ok"})
    except Exception as exc:
        logger.exception("Ошибка вебхука ЮKassa")
        return _json_response({"error": str(exc)}, status=400)


def _json_response(data, status=200):
    from django.http import JsonResponse

    return JsonResponse(data, status=status)
