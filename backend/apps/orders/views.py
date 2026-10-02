from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view

from config.responses import fail, ok
from apps.pricing.models import Option, OptionGroup
from apps.promo.models import PromoCode


@api_view(["POST"])
def quote(request):
    spec = request.data.get("spec") or {}
    promo_code = (request.data.get("promo_code") or "").strip()
    delivery_date = request.data.get("delivery_date")
    delivery_time = request.data.get("delivery_time")

    if not delivery_date:
        return fail({"delivery_date": "Укажите дату доставки"})
    if not delivery_time:
        return fail({"delivery_time": "Укажите время доставки"})

    if not (settings.DELIVERY_FROM <= delivery_time <= settings.DELIVERY_TO):
        return fail({
            "delivery_time": f"Доставка работает с {settings.DELIVERY_FROM} до {settings.DELIVERY_TO}"
        })

    items = []
    groups = {g.code: g for g in OptionGroup.objects.all()}

    for code, value in spec.items():
        if code == "inscription":
            if value:
                items.append({"title": "Надпись", "price": settings.INSCRIPTION_PRICE})
            continue

        group = groups.get(code)
        if not group:
            continue

        try:
            option = Option.objects.get(id=value, group=group, is_available=True)
        except Option.DoesNotExist:
            return fail({code: f"Опция с id={value} не найдена"})

        items.append({"title": option.title, "price": option.price_delta})

    subtotal = sum(item["price"] for item in items)

    try:
        delivery_dt = datetime.combine(
            date.fromisoformat(delivery_date),
            time.fromisoformat(delivery_time),
        )
        delivery_dt = timezone.make_aware(delivery_dt)
    except (ValueError, TypeError):
        return fail({"delivery_date": "Неверный формат даты или времени"})

    deadline = timezone.now() + timedelta(hours=settings.LEAD_TIME_HOURS)
    is_rush = delivery_dt < deadline

    rush_amount = 0
    if is_rush:
        rush_amount = round(subtotal * settings.RUSH_SURCHARGE_PERCENT / 100)

    discount = 0
    if promo_code:
        try:
            promo = PromoCode.objects.get(code=promo_code, active=True)
            discount = round((subtotal + rush_amount) * promo.percent / 100)
        except PromoCode.DoesNotExist:
            return fail({"promo_code": "Промокод не найден или неактивен"})

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
