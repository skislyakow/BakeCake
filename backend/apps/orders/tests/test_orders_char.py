import json
from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from apps.catalog.models import Cake
from apps.orders.models import Order, OrderEvent
from apps.pricing.models import Option, OptionGroup
from apps.promo.models import PromoCode
from apps.users.models import Profile


def _setup_base_groups():
    levels = OptionGroup.objects.create(code="levels", title="Количество уровней", is_required=True, sort=1)
    o1 = Option.objects.create(group=levels, title="1 уровень", price_delta=400, is_available=True, sort=1)
    form = OptionGroup.objects.create(code="form", title="Форма торта", is_required=True, sort=2)
    o2 = Option.objects.create(group=form, title="Круг", price_delta=400, is_available=True, sort=1)
    topping = OptionGroup.objects.create(code="topping", title="Топпинг", is_required=True, sort=3)
    o3 = Option.objects.create(group=topping, title="Без топпинга", price_delta=0, is_available=True, sort=1)
    return {"levels": levels, "form": form, "topping": topping, "o1": o1, "o2": o2, "o3": o3}


def _spec(g):
    return {"levels": g["o1"].pk, "form": g["o2"].pk, "topping": g["o3"].pk}


@pytest.fixture
def fixed_now(monkeypatch):
    """Замораживает часы, чтобы срочность и даты в тестах были предсказуемы."""
    moment = timezone.make_aware(datetime(2026, 5, 4, 9, 0))
    monkeypatch.setattr(timezone, "now", lambda: moment)
    return moment


@pytest.mark.django_db
def test_quote_custom_ok(client):
    g = _setup_base_groups()
    resp = client.post(
        "/api/quote/",
        data=json.dumps(
            {
                "spec": {**_spec(g), "inscription": "Привет"},
                "delivery_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
                "delivery_time": "12:00",
            }
        ),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is True
    assert any(i["title"] == "Надпись" for i in data["items"])


@pytest.mark.django_db
def test_quote_rush_surcharge(client, fixed_now):
    g = _setup_base_groups()
    resp = client.post(
        "/api/quote/",
        data=json.dumps(
            {
                "spec": _spec(g),
                "delivery_date": fixed_now.date().isoformat(),
                "delivery_time": "12:00",
            }
        ),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is True
    assert data["is_rush"] is True
    assert data["rush_amount"] == 160
    assert data["total"] == 800 + 160


@pytest.mark.django_db
def test_quote_far_date_is_not_rush(client, fixed_now):
    g = _setup_base_groups()
    resp = client.post(
        "/api/quote/",
        data=json.dumps(
            {
                "spec": _spec(g),
                "delivery_date": (fixed_now.date() + timedelta(days=3)).isoformat(),
                "delivery_time": "12:00",
            }
        ),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is True
    assert data["is_rush"] is False
    assert data["rush_amount"] == 0


@pytest.mark.django_db
def test_quote_promo(client):
    g = _setup_base_groups()
    PromoCode.objects.create(code="SAVE10", percent=10, active=True)
    resp = client.post(
        "/api/quote/",
        data=json.dumps(
            {
                "spec": _spec(g),
                "delivery_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
                "delivery_time": "14:00",
                "promo_code": "save10",
            }
        ),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is True
    assert data["discount"] == 80


@pytest.mark.django_db
def test_quote_missing_required(client):
    OptionGroup.objects.create(code="levels", title="Количество уровней", is_required=True, sort=1)
    OptionGroup.objects.create(code="form", title="Форма торта", is_required=True, sort=2)
    OptionGroup.objects.create(code="topping", title="Топпинг", is_required=True, sort=3)
    resp = client.post(
        "/api/quote/",
        data=json.dumps({"spec": {}, "delivery_date": (timezone.localdate() + timedelta(days=1)).isoformat(), "delivery_time": "12:00"}),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is False
    assert "spec" in data["errors"]


@pytest.mark.django_db
def test_quote_reports_both_missing_slots(client):
    g = _setup_base_groups()
    resp = client.post(
        "/api/quote/",
        data=json.dumps({"spec": _spec(g)}),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is False
    assert set(data["errors"]) == {"delivery_date", "delivery_time"}


@pytest.mark.django_db
def test_quote_reports_invalid_formats(client):
    g = _setup_base_groups()
    resp = client.post(
        "/api/quote/",
        data=json.dumps({"spec": _spec(g), "delivery_date": "04.05.2026", "delivery_time": "полдень"}),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is False
    assert data["errors"] == {"delivery_time": "Неверный формат времени, ожидается ЧЧ:ММ"}


@pytest.mark.django_db
def test_quote_reports_invalid_date(client):
    g = _setup_base_groups()
    resp = client.post(
        "/api/quote/",
        data=json.dumps({"spec": _spec(g), "delivery_date": "04.05.2026", "delivery_time": "12:00"}),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is False
    assert data["errors"] == {"delivery_date": "Неверный формат даты, ожидается ГГГГ-ММ-ДД"}


@pytest.mark.django_db
def test_quote_checks_delivery_before_spec(client):
    resp = client.post(
        "/api/quote/",
        data=json.dumps({"spec": {}}),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is False
    assert "delivery_date" in data["errors"]
    assert "spec" not in data["errors"]


@pytest.mark.django_db
def test_create_order_creates_user_profile_order_event_pd_utm(client):
    g = _setup_base_groups()
    resp = client.post(
        "/api/orders/",
        data=json.dumps(
            {
                "name": "Иван",
                "phone": "+7 (900) 123-45-67",
                "email": "ivan@test.ru",
                "address": "ул. Тестовая, 1",
                "delivery_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
                "delivery_time": "15:00",
                "spec": _spec(g),
                "comment": "тест",
            }
        ),
        content_type="application/json",
        HTTP_X_FORWARDED_FOR="1.2.3.4",
    )
    data = resp.json()
    assert data["ok"] is True
    assert data["payment_url"] == ""
    order = Order.objects.get(number=data["number"])
    assert order.user.phone in ("79001234567", "+79001234567")
    assert Profile.objects.filter(user=order.user).exists()
    assert OrderEvent.objects.filter(order=order, kind=OrderEvent.Kind.STATUS, text="Заказ создан").exists()
    assert order.pd_consent_at is not None
    assert order.pd_consent_ip == "1.2.3.4"
    assert order.pd_version


@pytest.mark.django_db
def test_create_order_accepts_numeric_phone(client):
    g = _setup_base_groups()
    resp = client.post(
        "/api/orders/",
        data=json.dumps(
            {
                "phone": 89001234567,
                "delivery_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
                "delivery_time": "16:00",
                "spec": _spec(g),
            }
        ),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is True
    assert Order.objects.get(number=data["number"]).user.phone in ("89001234567", "+79001234567")


@pytest.mark.django_db
def test_create_order_with_cake_id_invalid_falls_back_to_spec(client):
    Cake.objects.create(name="Тестовый торт", slug="test-cake", price=1000, occasion="день рождения", is_active=True)
    g = _setup_base_groups()
    resp = client.post(
        "/api/orders/",
        data=json.dumps(
            {
                "phone": "89001234567",
                "delivery_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
                "delivery_time": "16:00",
                "cake_id": 9999,
                "spec": _spec(g),
            }
        ),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is True
    order = Order.objects.get(number=data["number"])
    assert order.spec.get("levels") == g["o1"].pk
