import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.catalog.models import Cake
from apps.pricing.models import Option, OptionGroup


def _groups():
    levels = OptionGroup.objects.create(code="levels", title="Количество уровней", is_required=True, sort=1)
    o1 = Option.objects.create(group=levels, title="1 уровень", price_delta=400, is_available=True, sort=1)
    form = OptionGroup.objects.create(code="form", title="Форма торта", is_required=True, sort=2)
    o2 = Option.objects.create(group=form, title="Круг", price_delta=400, is_available=True, sort=1)
    topping = OptionGroup.objects.create(code="topping", title="Топпинг", is_required=True, sort=3)
    o3 = Option.objects.create(group=topping, title="Без топпинга", price_delta=0, is_available=True, sort=1)
    return o1, o2, o3


def _place(client, **overrides):
    o1, o2, o3 = _groups()
    body = {
        "phone": "+79001234567",
        "address": "ул. Тестовая, 1",
        "delivery_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
        "delivery_time": "15:00",
        "spec": {"levels": o1.pk, "form": o2.pk, "topping": o3.pk, "inscription": "Привет"},
        "comment": "к заказу",
        "courier_comment": "курьеру",
    }
    body.update(overrides)
    return client.post("/api/orders/", data=json.dumps(body), content_type="application/json")


@pytest.mark.django_db
def test_order_detail_returns_repeat_spec_and_labels(client):
    placed = _place(client).json()
    number = placed["number"]

    resp = client.get(f"/api/orders/{number}/")

    data = resp.json()
    assert data["ok"] is True
    assert data["number"] == number
    assert data["status"] == "new"
    assert data["status_label"]
    assert data["spec_labels"] == ["1 уровень", "Круг", "Без топпинга", "Надпись"]
    assert data["spec"]["inscription"] == "Привет"
    assert {"levels", "form", "topping"} <= set(data["spec"])
    assert data["comment"] == "к заказу"
    assert data["courier_comment"] == "курьеру"
    assert data["address"] == "ул. Тестовая, 1"


@pytest.mark.django_db
def test_order_detail_for_cake_keeps_cake_spec(client):
    cake = Cake.objects.create(name="Тестовый торт", slug="test-cake-read", price=1000, occasion="день рождения", is_active=True)
    placed = _place(client, cake_id=cake.pk, spec=None).json()

    data = client.get(f"/api/orders/{placed['number']}/").json()

    assert data["ok"] is True
    assert data["spec"] == {"cake": cake.pk}
    assert data["spec_labels"] == ["Тестовый торт"]


@pytest.mark.django_db
def test_orders_list_uses_same_labels_without_full_spec(client):
    placed = _place(client).json()

    data = client.get("/api/orders/").json()

    assert data["ok"] is True
    item = next(i for i in data["items"] if i["number"] == placed["number"])
    assert item["spec_labels"] == ["1 уровень", "Круг", "Без топпинга", "Надпись"]
    assert "spec" not in item
    assert "comment" not in item
