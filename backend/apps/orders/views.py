from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import (
    get_user_model,
    login as auth_login,
)
from django.utils import timezone
from rest_framework.decorators import api_view

from config.responses import fail, ok
from apps.orders.models import Issue, Order, OrderEvent
from apps.pricing.models import Option, OptionGroup
from apps.promo.models import PromoCode
from apps.users.models import Profile

User = get_user_model()


def _as_time(value):
    try:
        return time.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def _as_date(value):
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def _calculate(spec, delivery_date, delivery_time, promo_code=""):
    """Валидирует спецификацию и сроки доставки, считает сумму. Возвращает
    (данные для ok, errors-словарь). Ровно одна из двух частей непустая."""
    if not isinstance(spec, dict):
        return None, {"spec": "Ожидается объект вида {код группы: id опции}"}

    missing = {}
    if not delivery_date:
        missing["delivery_date"] = "Укажите дату доставки"
    if not delivery_time:
        missing["delivery_time"] = "Укажите время доставки"
    if missing:
        return None, missing

    delivery_t = _as_time(delivery_time)
    if delivery_t is None:
        return None, {"delivery_time": "Неверный формат времени, ожидается ЧЧ:ММ"}

    window_from = _as_time(settings.DELIVERY_FROM)
    window_to = _as_time(settings.DELIVERY_TO)
    if not (window_from <= delivery_t <= window_to):
        return None, {
            "delivery_time": f"Доставка работает с {settings.DELIVERY_FROM} до {settings.DELIVERY_TO}"
        }

    delivery_d = _as_date(delivery_date)
    if delivery_d is None:
        return None, {"delivery_date": "Неверный формат даты, ожидается ГГГГ-ММ-ДД"}
    if delivery_d < timezone.localdate():
        return None, {"delivery_date": "Дата доставки не может быть в прошлом"}

    chosen = {code: value for code, value in spec.items() if value not in (None, "", 0)}

    groups = {g.code: g for g in OptionGroup.objects.all()}

    items = []
    errors = {}
    for code, value in chosen.items():
        if code == "inscription":
            if not isinstance(value, str):
                errors["inscription"] = "Надпись должна быть строкой"
            elif value.strip():
                items.append({"title": "Надпись", "price": settings.INSCRIPTION_PRICE})
            continue

        group = groups.get(code)
        if not group:
            errors[code] = "Неизвестная группа опций"
            continue

        if isinstance(value, bool) or not isinstance(value, int):
            errors[code] = f"Ожидается id опции для группы «{group.title}»"
            continue

        try:
            option = Option.objects.get(id=value, group=group, is_available=True)
        except Option.DoesNotExist:
            errors[code] = f"Опция с id={value} не найдена"
            continue

        items.append({"title": option.title, "price": option.price_delta})

    not_chosen = sorted(g.title for g in groups.values() if g.is_required and g.code not in chosen)
    if not_chosen:
        errors["spec"] = "Не выбрано: " + ", ".join(not_chosen)

    if errors:
        return None, errors

    subtotal = sum(item["price"] for item in items)

    delivery_dt = timezone.make_aware(datetime.combine(delivery_d, delivery_t))
    is_rush = delivery_dt < timezone.now() + timedelta(hours=settings.LEAD_TIME_HOURS)

    rush_amount = 0
    if is_rush:
        rush_amount = round(subtotal * settings.RUSH_SURCHARGE_PERCENT / 100)

    promo = None
    discount = 0
    code = (promo_code or "").strip()
    if code:
        try:
            promo = PromoCode.objects.get(code__iexact=code, active=True)
        except PromoCode.DoesNotExist:
            return None, {"promo_code": "Промокод не найден или неактивен"}
        discount = round((subtotal + rush_amount) * promo.percent / 100)

    total = subtotal + rush_amount - discount

    return {
        "items": items,
        "subtotal": subtotal,
        "is_rush": is_rush,
        "rush_amount": rush_amount,
        "discount": discount,
        "total": total,
        "promo": promo,
        "delivery_date": delivery_d,
        "delivery_time": delivery_t,
    }, None


@api_view(["POST"])
def quote(request):
    data, errors = _calculate(
        request.data.get("spec"),
        request.data.get("delivery_date"),
        request.data.get("delivery_time"),
        request.data.get("promo_code"),
    )
    if errors:
        return fail(errors)

    return ok(
        items=data["items"],
        subtotal=data["subtotal"],
        is_rush=data["is_rush"],
        rush_amount=data["rush_amount"],
        discount=data["discount"],
        total=data["total"],
    )

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
    phone = (body.get("phone") or "").strip()
    if not phone:
        return fail({"phone": "Введите номер телефона"})

    data, errors = _calculate(
        body.get("spec"),
        body.get("delivery_date"),
        body.get("delivery_time"),
        body.get("promo_code"),
    )
    if errors:
        return fail(errors)

    user, _ = User.objects.get_or_create(phone=phone)
    name = (body.get("name") or "").strip()
    email = (body.get("email") or "").strip()
    if name:
        user.name = name
    if email:
        user.email = email
    user.save()

    profile, _ = Profile.objects.get_or_create(user=user)
    address = (body.get("address") or "").strip()
    if address:
        profile.default_address = address
        profile.save()

    if not request.user.is_authenticated or request.user.id != user.id:
        auth_login(request, user)

    if not request.session.session_key:
        request.session.create()

    order = Order.objects.create(
        user=user,
        spec={k: v for k, v in (body.get("spec") or {}).items() if v not in (None, "", 0)},
        price_items=data["items"],
        subtotal=data["subtotal"],
        total=data["total"],
        discount=data["discount"],
        promo=data["promo"],
        delivery_date=data["delivery_date"],
        delivery_time=data["delivery_time"],
        is_rush=data["is_rush"],
        rush_amount=data["rush_amount"],
        address=address,
        comment=(body.get("comment") or "").strip(),
        courier_comment=(body.get("courier_comment") or "").strip(),
        pd_consent_at=timezone.now(),
        pd_consent_ip=_client_ip(request),
        pd_version=_pd_version(),
        utm_source=request.COOKIES.get("bc_utm", ""),
        session_key=request.session.session_key,
    )
    OrderEvent.objects.create(order=order, kind=OrderEvent.Kind.STATUS, text="Заказ создан")

    return ok(
        number=order.number,
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
