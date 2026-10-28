from django.conf import settings
from django.contrib.auth import (
    get_user_model,
    login as auth_login,
)
from django.utils import timezone
from rest_framework.decorators import api_view

from config.responses import fail, ok
from apps.analytics.views import _read_first_touch
from apps.orders.models import Issue, Order
from apps.users.utils import normalize_phone
from apps.orders import intake
from apps.orders.intake import OrderIntakeError
from apps.orders.intake import pricing as intake_pricing

User = get_user_model()


@api_view(["POST"])
def quote(request):
    try:
        draft = intake.parse_draft(request.data)
        now = timezone.now()
        rules = intake_pricing._rules_from_settings()
        q = intake.price_order(draft, rules=rules, now=now)
        return ok(
            items=q.items,
            subtotal=q.subtotal,
            is_rush=q.is_rush,
            rush_amount=q.rush_amount,
            discount=q.discount,
            total=q.total,
        )
    except OrderIntakeError as exc:
        return fail(exc.errors)

def _spec_labels(order):
    return [item["title"] for item in order.price_items if isinstance(item, dict) and item.get("title")]


def _serialize(order, full=False):
    data = {
        "number": order.number,
        "status": order.status,
        "status_label": order.get_status_display(),  # pyright: ignore[reportAttributeAccessIssue]
        "spec_labels": _spec_labels(order),
        "total": order.total,
        "delivery_date": order.delivery_date.isoformat(),
        "delivery_time": order.delivery_time.strftime("%H:%M"),
        "address": order.address,
        "is_rush": order.is_rush,
        "is_rescheduled": order.is_rescheduled,
        "reschedule_note": order.reschedule_note,
    }
    if full:
        data.update(
            spec=order.spec,
            comment=order.comment,
            courier_comment=order.courier_comment,
        )
    return data





def _user_order_or_fail(request, number):
    if not request.user.is_authenticated:
        return fail({"auth": "Не авторизован"}), None
    order = request.user.orders.filter(number=str(number)).first()
    if order is None:
        return fail({"number": "Заказ не найден"}), None
    return None, order


def _client_ip(request):
    return request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")


def _pd_version():
    return getattr(settings, "PD_VERSION", "")


@api_view(["GET", "POST"])
def orders(request):
    if request.method == "GET":
        if not request.user.is_authenticated:
            return fail({"auth": "Не авторизован"})
        items = [_serialize(order) for order in request.user.orders.order_by("-created")]
        return ok(items=items)

    body = request.data
    phone = normalize_phone(body.get("phone"))
    if not phone:
        return fail({"phone": "Введите номер телефона"})

    try:
        draft = intake.parse_draft(body)
        now = timezone.now()
        rules = intake_pricing._rules_from_settings()
        if not request.session.session_key:
            request.session.create()
        utm_source, utm_medium, utm_campaign = _read_first_touch(request)
        ctx = intake.RequestContext(
            ip=_client_ip(request),
            session_key=request.session.session_key or "",
            actor=request.user if getattr(request.user, "is_authenticated", False) else None,
            attribution=(utm_source, utm_medium, utm_campaign),
            pd_version=_pd_version(),
            now=now,
        )
        placed = intake.place_order(draft, ctx, rules=rules)
        user = placed.order.user
    except OrderIntakeError as exc:
        return fail(exc.errors)

    if not request.user.is_authenticated or request.user.id != user.id:
        auth_login(request, user)

    order = placed.order

    return ok(
        number=order.number,
        order_id=order.pk,
        total=order.total,
        is_rush=order.is_rush,
        payment_url="",
    )


@api_view(["GET"])
def order_detail(request, number):
    error, order = _user_order_or_fail(request, number)
    if error is not None:
        return error
    return ok(**_serialize(order, full=True))


@api_view(["POST"])
def order_issue(request, number):
    error, order = _user_order_or_fail(request, number)
    if error is not None:
        return error

    message = (request.data.get("message") or "").strip()
    if not message:
        return fail({"message": "Напишите, что случилось"})

    Issue.objects.create(order=order, message=message)
    return ok()
