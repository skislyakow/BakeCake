import json
import logging

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status as http_status
from rest_framework.decorators import api_view

from config.responses import fail, ok

from .gateway import PaymentError, handle_webhook, start_payment

logger = logging.getLogger(__name__)


@api_view(["POST"])
def create_payment(request, order_id):
    """Создать платёж и вернуть ссылку на оплату (или повторный pending-платёж)."""
    if not request.user.is_authenticated:
        return fail({"auth": "Не авторизован"}, status=http_status.HTTP_401_UNAUTHORIZED)

    order = request.user.orders.filter(pk=order_id).first()
    if order is None:
        return fail({"order": "Заказ не найден"}, status=http_status.HTTP_404_NOT_FOUND)

    return_url = f"{settings.SITE_URL}/orders/?order={order.number}&paid=1"
    try:
        payment = start_payment(order, return_url=return_url)
    except PaymentError as exc:
        return fail(exc.errors, status=exc.status)
    return ok(confirmation_url=payment.confirmation_url)


@csrf_exempt
def webhook(request):
    """Уведомление от платёжной системы о смене статуса платежа."""
    if request.method != "POST":
        return _json_response({"error": "POST required"}, status=400)
    try:
        payload = json.loads(request.body)
        handle_webhook(payload)
        return _json_response({"status": "ok"})
    except Exception as exc:
        logger.exception("Ошибка вебхука платёжной системы")
        return _json_response({"error": str(exc)}, status=400)


def _json_response(data, status=200):
    from django.http import JsonResponse

    return JsonResponse(data, status=status)
