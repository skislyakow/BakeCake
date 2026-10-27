import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.catalog.models import Cake
from apps.orders.models import Order, OrderEvent
from apps.pricing.models import Option, OptionGroup
from apps.promo.models import PromoCode
from apps.users.models import Profile

User = get_user_model()


def _setup_base_groups():
    levels = OptionGroup.objects.create(code="levels", title="Количество уровней", is_required=True, sort=1)
    o1 = Option.objects.create(group=levels, title="1 уровень", price_delta=400, is_available=True, sort=1)
    form = OptionGroup.objects.create(code="form", title="Форма торта", is_required=True, sort=2)
    o2 = Option.objects.create(group=form, title="Круг", price_delta=400, is_available=True, sort=1)
    topping = OptionGroup.objects.create(code="topping", title="Топпинг", is_required=True, sort=3)
    o3 = Option.objects.create(group=topping, title="Без топпинга", price_delta=0, is_available=True, sort=1)
    return {"levels": levels, "form": form, "topping": topping, "o1": o1, "o2": o2, "o3": o3}


@pytest.mark.django_db
def test_quote_custom_ok(client):
    g = _setup_base_groups()
    resp = client.post(
        "/api/quote/",
        data=json.dumps(
            {
                "spec": {"levels": g["o1"].id, "form": g["o2"].id, "topping": g["o3"].id, "inscription": "Привет"},
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
def test_quote_rush_surcharge(client):
    g = _setup_base_groups()
    now = timezone.now()
    soon = now + timedelta(hours=2)
    resp = client.post(
        "/api/quote/",
        data=json.dumps(
            {
                "spec": {"levels": g["o1"].id, "form": g["o2"].id, "topping": g["o3"].id},
                "delivery_date": soon.date().isoformat(),
                "delivery_time": soon.time().strftime("%H:%M"),
            }
        ),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is True
    assert data["is_rush"] is True
    assert data["rush_amount"] == 160


@pytest.mark.django_db
def test_quote_promo(client):
    g = _setup_base_groups()
    PromoCode.objects.create(code="SAVE10", percent=10, active=True)
    resp = client.post(
        "/api/quote/",
        data=json.dumps(
            {
                "spec": {"levels": g["o1"].id, "form": g["o2"].id, "topping": g["o3"].id},
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
                "spec": {"levels": g["o1"].id, "form": g["o2"].id, "topping": g["o3"].id},
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
                "spec": {"levels": g["o1"].id, "form": g["o2"].id, "topping": g["o3"].id},
            }
        ),
        content_type="application/json",
    )
    data = resp.json()
    assert data["ok"] is True
    order = Order.objects.get(number=data["number"])
    assert order.spec.get("levels") == g["o1"].id
