from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from apps.catalog.models import Cake
from apps.orders.intake import (
    OrderIntakeError,
    RequestContext,
    parse_draft,
    parse_rules,
    place_order,
    price_order,
)
from apps.orders.models import Order, OrderEvent
from apps.pricing.models import Option, OptionGroup
from apps.promo.models import PromoCode
from apps.users.models import Profile


def _groups():
    levels = OptionGroup.objects.create(code="levels", title="Количество уровней", is_required=True, sort=1)
    form = OptionGroup.objects.create(code="form", title="Форма торта", is_required=True, sort=2)
    topping = OptionGroup.objects.create(code="topping", title="Топпинг", is_required=True, sort=3)
    return {
        "levels": Option.objects.create(group=levels, title="1 уровень", price_delta=400, is_available=True, sort=1),
        "form": Option.objects.create(group=form, title="Круг", price_delta=400, is_available=True, sort=1),
        "topping": Option.objects.create(group=topping, title="Без топпинга", price_delta=0, is_available=True, sort=1),
    }


def _payload(**overrides):
    choices = _groups()
    payload = {
        "phone": "+7 900 111-22-33",
        "name": "Тест",
        "email": "test@example.com",
        "address": "ул. Тестовая, 1",
        "spec": {code: option.pk for code, option in choices.items()},
        "delivery_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
        "delivery_time": "15:00",
    }
    payload.update(overrides)
    return payload, choices


def _context(**overrides):
    values = {
        "ip": "9.9.9.9",
        "session_key": "session-1",
        "attribution": ("yandex", "cpc", "spring"),
        "pd_version": "1.0",
        "now": timezone.now(),
    }
    values.update(overrides)
    return RequestContext(**values)


@pytest.mark.django_db
def test_price_custom_subtotal_and_inscription():
    payload, choices = _payload()
    spec = {code: option.pk for code, option in choices.items()}
    draft = parse_draft({**payload, "spec": {**spec, "inscription": "С днём рождения"}})

    quote = price_order(draft, now=timezone.now())

    assert quote.subtotal == 400 + 400 + 0 + 500
    assert quote.total == quote.subtotal + quote.rush_amount - quote.discount
    assert any(item["title"] == "Надпись" and item["price"] == 500 for item in quote.items)


@pytest.mark.django_db
def test_price_cake_uses_catalog_price():
    cake = Cake.objects.create(name="Готовый", slug="ready", price=1500, occasion="день рождения", is_active=True)
    draft = parse_draft(
        {
            "cake_id": cake.pk,
            "delivery_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
            "delivery_time": "12:00",
        }
    )

    quote = price_order(draft, now=timezone.now())

    assert quote.subtotal == 1500
    assert quote.items == [{"title": "Готовый", "price": 1500, "cake": cake.pk}]


@pytest.mark.django_db
def test_price_rejects_inactive_promo():
    payload, _ = _payload()
    draft = parse_draft({**payload, "promo_code": "BAD"})

    with pytest.raises(OrderIntakeError) as exc:
        price_order(draft, now=timezone.now())

    assert "promo_code" in exc.value.errors


@pytest.mark.django_db
def test_price_applies_promo_case_insensitively():
    payload, _ = _payload()
    PromoCode.objects.create(code="SAVE10", percent=10, active=True)
    draft = parse_draft({**payload, "promo_code": "save10"})

    quote = price_order(draft, now=timezone.now())

    assert quote.discount == 80
    assert quote.total == quote.subtotal + quote.rush_amount - 80


@pytest.mark.django_db
def test_price_requires_delivery_slot():
    payload, _ = _payload(delivery_date=None, delivery_time=None)

    with pytest.raises(OrderIntakeError) as exc:
        price_order(parse_draft(payload), now=timezone.now())

    assert set(exc.value.errors) == {"delivery_date", "delivery_time"}


@pytest.mark.django_db
def test_price_prefers_delivery_errors_over_spec_errors():
    payload, _ = _payload(spec={}, delivery_time="полдень")

    with pytest.raises(OrderIntakeError) as exc:
        price_order(parse_draft(payload), now=timezone.now())

    assert exc.value.errors == {"delivery_time": "Неверный формат времени, ожидается ЧЧ:ММ"}


def test_parse_rules_reads_settings():
    rules = parse_rules()

    assert rules.delivery_from.isoformat() == settings.DELIVERY_FROM + ":00"
    assert rules.delivery_to.isoformat() == settings.DELIVERY_TO + ":00"
    assert rules.lead_time_hours == settings.LEAD_TIME_HOURS
    assert rules.rush_surcharge_percent == settings.RUSH_SURCHARGE_PERCENT
    assert rules.inscription_price == settings.INSCRIPTION_PRICE


@pytest.mark.django_db
def test_place_order_creates_related_records():
    payload, _ = _payload()

    placed = place_order(parse_draft(payload), _context())

    order = placed.order
    assert isinstance(order, Order)
    assert order.user.phone in ("79001112233", "+79001112233")
    assert Profile.objects.filter(user=order.user).exists()
    assert OrderEvent.objects.filter(order=order, text="Заказ создан").exists()
    assert order.pd_consent_ip == "9.9.9.9"
    assert order.pd_version == "1.0"
    assert (order.utm_source, order.utm_medium, order.utm_campaign) == ("yandex", "cpc", "spring")
    assert order.session_key == "session-1"
    assert order.total == placed.quote.total


@pytest.mark.django_db
def test_place_order_with_unknown_cake_falls_back_to_spec():
    payload, choices = _payload(cake_id=9999)

    placed = place_order(parse_draft(payload), _context())

    assert placed.order.spec == {code: option.pk for code, option in choices.items()}
    assert placed.order.subtotal == 800


@pytest.mark.django_db
def test_place_order_without_phone_creates_nothing():
    payload, _ = _payload(phone="")
    draft = parse_draft(payload)

    with pytest.raises(OrderIntakeError) as exc:
        place_order(draft, _context())

    assert "phone" in exc.value.errors
    assert Order.objects.count() == 0
