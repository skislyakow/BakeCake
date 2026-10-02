from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view

from config.responses import fail, ok
from apps.pricing.models import Option, OptionGroup
from apps.promo.models import PromoCode


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


@api_view(["POST"])
def quote(request):
    spec = request.data.get("spec")
    if spec is None:
        spec = {}
    if not isinstance(spec, dict):
        return fail({"spec": "Ожидается объект вида {код группы: id опции}"})

    delivery_date = request.data.get("delivery_date")
    delivery_time = request.data.get("delivery_time")
    missing = {}
    if not delivery_date:
        missing["delivery_date"] = "Укажите дату доставки"
    if not delivery_time:
        missing["delivery_time"] = "Укажите время доставки"
    if missing:
        return fail(missing)

    delivery_t = _as_time(delivery_time)
    if delivery_t is None:
        return fail({"delivery_time": "Неверный формат времени, ожидается ЧЧ:ММ"})

    window_from = _as_time(settings.DELIVERY_FROM)
    window_to = _as_time(settings.DELIVERY_TO)
    if not (window_from <= delivery_t <= window_to):
        return fail({
            "delivery_time": f"Доставка работает с {settings.DELIVERY_FROM} до {settings.DELIVERY_TO}"
        })

    delivery_d = _as_date(delivery_date)
    if delivery_d is None:
        return fail({"delivery_date": "Неверный формат даты, ожидается ГГГГ-ММ-ДД"})
    if delivery_d < timezone.localdate():
        return fail({"delivery_date": "Дата доставки не может быть в прошлом"})

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
        return fail(errors)

    subtotal = sum(item["price"] for item in items)

    delivery_dt = timezone.make_aware(datetime.combine(delivery_d, delivery_t))
    is_rush = delivery_dt < timezone.now() + timedelta(hours=settings.LEAD_TIME_HOURS)

    rush_amount = 0
    if is_rush:
        rush_amount = round(subtotal * settings.RUSH_SURCHARGE_PERCENT / 100)

    discount = 0
    promo_code = (request.data.get("promo_code") or "").strip()
    if promo_code:
        try:
            promo = PromoCode.objects.get(code__iexact=promo_code, active=True)
        except PromoCode.DoesNotExist:
            return fail({"promo_code": "Промокод не найден или неактивен"})
        discount = round((subtotal + rush_amount) * promo.percent / 100)

    total = subtotal + rush_amount - discount

    return ok(
        items=items,
        subtotal=subtotal,
        is_rush=is_rush,
        rush_amount=rush_amount,
        discount=discount,
        total=total,
    )

def _created_order_response():
    return ok(number="2239400223", total=2367, is_rush=False, payment_url="")


def _order_list_response():
    return ok(items=[])


@api_view(["GET", "POST"])
def orders(request):
    if request.method == "POST":
        return _created_order_response()
    return _order_list_response()


@api_view(["GET"])
def order_detail(request, number):
    return ok(
        number=str(number),
        status="paid",
        status_label="Оплачен",
        spec={},
        spec_labels=[],
        total=2367,
        delivery_date="2026-10-05",
        delivery_time="12:00",
        is_rush=False,
        is_rescheduled=True,
        reschedule_note="Новые сроки: 16:00",
        comment="",
        courier_comment="звонить за час",
    )


@api_view(["POST"])
def order_issue(request, number):
    return ok()
