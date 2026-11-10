from datetime import date, datetime, time, timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Cake
from apps.orders.models import Order, OrderEvent
from apps.pricing.models import Option, OptionGroup
from apps.promo.models import PromoCode
from apps.users.customer import CustomerData, identify_customer
from apps.users.utils import normalize_phone

from .errors import OrderIntakeError
from .types import (
    CakeChoice,
    CustomChoice,
    OrderDraft,
    OrderSelection,
    PlacedOrder,
    PricingRules,
    Quote,
    RequestContext,
)

SPEC_ERROR = "Ожидается объект вида {код группы: id опции}"


def parse_rules() -> PricingRules:
    """Собирает правила расчёта из настроек проекта."""
    return PricingRules(
        delivery_from=time.fromisoformat(settings.DELIVERY_FROM),
        delivery_to=time.fromisoformat(settings.DELIVERY_TO),
        lead_time_hours=int(settings.LEAD_TIME_HOURS),
        rush_surcharge_percent=int(settings.RUSH_SURCHARGE_PERCENT),
        inscription_price=int(settings.INSCRIPTION_PRICE),
    )


def _spec_items(spec: dict[str, Any], inscription_price: int) -> list[dict[str, Any]]:
    """Считает позиции заказа по выбранным опциям. Raises OrderIntakeError."""
    groups = {group.code: group for group in OptionGroup.objects.all()}

    items: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    for code, value in spec.items():
        if code == "inscription":
            if not isinstance(value, str):
                errors["inscription"] = "Надпись должна быть строкой"
            elif value.strip():
                items.append({"title": "Надпись", "price": inscription_price})
            continue

        group = groups.get(code)
        if group is None:
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

    not_chosen = sorted(group.title for group in groups.values() if group.is_required and group.code not in spec)
    if not_chosen:
        errors["spec"] = "Не выбрано: " + ", ".join(not_chosen)

    if errors:
        raise OrderIntakeError(errors)

    return items


def _clean_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {code: value for code, value in spec.items() if value not in (None, "", 0)}


def _selection(
    selection: OrderSelection,
    spec_raw: dict[str, Any],
    inscription_price: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Возвращает позиции заказа и spec, который нужно сохранить в заказе."""
    if isinstance(selection, CakeChoice):
        cake = Cake.objects.filter(pk=selection.cake_id, is_active=True).first()
        if cake is not None:
            return [{"title": cake.name, "price": cake.price, "cake": cake.pk}], {"cake": cake.pk}
        # preserve behavior: unknown/inactive cake_id falls back to the spec path
        spec = _clean_spec(spec_raw)
        return _spec_items(spec, inscription_price), spec

    if isinstance(selection, CustomChoice):
        spec = _clean_spec(selection.spec)
        return _spec_items(spec, inscription_price), spec

    raise OrderIntakeError({"spec": SPEC_ERROR})


def _delivery_moment(draft: OrderDraft, rules: PricingRules, now: datetime) -> tuple[date, time, datetime]:
    missing = {}
    if not draft.delivery_date_raw:
        missing["delivery_date"] = "Укажите дату доставки"
    if not draft.delivery_time_raw:
        missing["delivery_time"] = "Укажите время доставки"
    if missing:
        raise OrderIntakeError(missing)

    if draft.delivery_time is None:
        raise OrderIntakeError({"delivery_time": "Неверный формат времени, ожидается ЧЧ:ММ"})

    delivery_time = draft.delivery_time
    if not (rules.delivery_from <= delivery_time <= rules.delivery_to):
        raise OrderIntakeError(
            {
                "delivery_time": (
                    f"Доставка работает с {rules.delivery_from.strftime('%H:%M')} "
                    f"до {rules.delivery_to.strftime('%H:%M')}"
                )
            }
        )

    if draft.delivery_date is None:
        raise OrderIntakeError({"delivery_date": "Неверный формат даты, ожидается ГГГГ-ММ-ДД"})

    delivery_date = draft.delivery_date
    if delivery_date < timezone.localdate(now):
        raise OrderIntakeError({"delivery_date": "Дата доставки не может быть в прошлом"})

    moment = timezone.make_aware(datetime.combine(delivery_date, delivery_time))
    return delivery_date, delivery_time, moment


def _resolve_promo(promo_code: str) -> PromoCode | None:
    code = (promo_code or "").strip()
    if not code:
        return None
    try:
        return PromoCode.objects.get(code__iexact=code, active=True)
    except PromoCode.DoesNotExist:
        raise OrderIntakeError({"promo_code": "Промокод не найден или неактивен"}) from None


def _price(draft: OrderDraft, rules: PricingRules, now: datetime) -> tuple[Quote, dict[str, Any]]:
    delivery_date, delivery_time, moment = _delivery_moment(draft, rules, now)
    items, spec = _selection(draft.selection, draft.spec_raw or {}, rules.inscription_price)

    subtotal = sum(item["price"] for item in items)

    is_rush = moment < now + timedelta(hours=rules.lead_time_hours)
    rush_amount = round(subtotal * rules.rush_surcharge_percent / 100) if is_rush else 0

    promo = _resolve_promo(draft.promo_code)
    discount = round((subtotal + rush_amount) * promo.percent / 100) if promo is not None else 0

    return Quote(
        items=items,
        subtotal=subtotal,
        is_rush=is_rush,
        rush_amount=rush_amount,
        discount=discount,
        total=subtotal + rush_amount - discount,
        promo=promo,
        delivery_date=delivery_date,
        delivery_time=delivery_time,
    ), spec


def price_order(draft: OrderDraft, rules: PricingRules | None = None, now: datetime | None = None) -> Quote:
    """Считает стоимость заказа без побочных эффектов."""
    quote, _ = _price(draft, rules or parse_rules(), now or timezone.now())
    return quote


def place_order(
    draft: OrderDraft,
    context: RequestContext,
    rules: PricingRules | None = None,
) -> PlacedOrder:
    """Считает заказ и сохраняет его вместе с покупателем и событием в одной транзакции."""
    now = context.now or timezone.now()

    phone = normalize_phone(draft.phone) or normalize_phone(getattr(context.actor, "phone", "") or "")
    if not phone:
        raise OrderIntakeError({"phone": "Введите номер телефона"})
    if not draft.pd_consent:
        raise OrderIntakeError({"pd_consent": "Подтвердите согласие на обработку персональных данных"})

    quote, spec = _price(draft, rules or parse_rules(), now)

    utm_source, utm_medium, utm_campaign = context.attribution

    address = draft.address.strip()
    comment = draft.comment.strip()
    courier_comment = draft.courier_comment.strip()

    with transaction.atomic():
        customer = identify_customer(
            phone,
            CustomerData(name=draft.name, email=draft.email, default_address=address),
        )

        order = Order.objects.create(
            user=customer,
            spec=spec,
            price_items=quote.items,
            subtotal=quote.subtotal,
            total=quote.total,
            discount=quote.discount,
            promo=quote.promo,
            delivery_date=quote.delivery_date,
            delivery_time=quote.delivery_time,
            is_rush=quote.is_rush,
            rush_amount=quote.rush_amount,
            address=address,
            comment=comment,
            courier_comment=courier_comment,
            pd_consent_at=now,
            pd_consent_ip=context.ip,
            pd_version=context.pd_version,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            session_key=context.session_key,
        )
        OrderEvent.objects.create(order=order, kind=OrderEvent.Kind.STATUS, text="Заказ создан")

    return PlacedOrder(order=order, quote=quote)
