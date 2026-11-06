import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.orders.models import Order
from apps.pricing.models import Option, OptionGroup
from apps.users.models import Profile, User


def _login(client, phone):
    return client.post(
        "/api/auth/login/",
        data=json.dumps({"phone": phone}),
        content_type="application/json",
    )


def _groups():
    groups = {}
    for sort, code in enumerate(("levels", "form", "topping"), start=1):
        group = OptionGroup.objects.create(code=code, title=code, is_required=True, sort=sort)
        groups[code] = Option.objects.create(group=group, title=f"{code} 1", price_delta=100, is_available=True, sort=1)
    return {code: option.pk for code, option in groups.items()}


def _order_body(**overrides):
    body = {
        "phone": "8 (900) 777-66-55",
        "delivery_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
        "delivery_time": "15:00",
        "spec": _groups(),
    }
    body.update(overrides)
    return body


@pytest.mark.django_db
def test_login_creates_customer_with_profile(client):
    resp = _login(client, "8 (900) 777-66-55")

    data = resp.json()
    assert data["ok"] is True
    assert data["user"]["phone"] == "+79007776655"
    user = User.objects.get(phone="+79007776655")
    assert Profile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_login_matches_existing_customer_across_phone_formats(client):
    _login(client, "8 (900) 777-66-55")
    _login(client, "+7 900 777 66 55")

    assert User.objects.count() == 1


@pytest.mark.django_db
def test_login_without_phone_fails(client):
    resp = _login(client, "")

    data = resp.json()
    assert data["ok"] is False
    assert data["errors"] == {"phone": "Введите номер телефона"}
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_profile_patch_updates_fields(client):
    _login(client, "+79007776655")

    resp = client.patch("/api/me/", data=json.dumps({"name": "Ирина", "email": "i@example.com", "default_address": "ул. А, 1"}), content_type="application/json")

    data = resp.json()
    assert data == {
        "ok": True,
        "phone": "+79007776655",
        "name": "Ирина",
        "email": "i@example.com",
        "default_address": "ул. А, 1",
    }


@pytest.mark.django_db
def test_profile_patch_clears_fields_with_empty_string(client):
    _login(client, "+79007776655")
    client.patch("/api/me/", data=json.dumps({"name": "Ирина", "email": "i@example.com"}), content_type="application/json")

    resp = client.patch("/api/me/", data=json.dumps({"name": "", "email": ""}), content_type="application/json")

    data = resp.json()
    assert data["name"] == ""
    assert data["email"] == ""


@pytest.mark.django_db
def test_profile_patch_leaves_untouched_fields(client):
    _login(client, "+79007776655")
    client.patch("/api/me/", data=json.dumps({"name": "Ирина", "email": "i@example.com"}), content_type="application/json")

    resp = client.patch("/api/me/", data=json.dumps({"default_address": "ул. Б, 2"}), content_type="application/json")

    data = resp.json()
    assert data["name"] == "Ирина"
    assert data["email"] == "i@example.com"
    assert data["default_address"] == "ул. Б, 2"


@pytest.mark.django_db
def test_checkout_fills_customer_and_default_address(client):
    resp = client.post(
        "/api/orders/",
        data=json.dumps(_order_body(name="Пётр", email="p@example.com", address="ул. В, 3")),
        content_type="application/json",
    )

    assert resp.json()["ok"] is True
    user = Order.objects.get().user
    assert user.phone == "+79007776655"
    assert user.name == "Пётр"
    assert user.email == "p@example.com"
    assert Profile.objects.get(user=user).default_address == "ул. В, 3"


@pytest.mark.django_db
def test_checkout_does_not_erase_existing_customer_fields(client):
    user = User.objects.create(phone="+79007776655", name="Ирина", email="i@example.com")
    Profile.objects.create(user=user, default_address="ул. Старая, 1")

    resp = client.post(
        "/api/orders/",
        data=json.dumps(_order_body(name="", email="", address="")),
        content_type="application/json",
    )

    assert resp.json()["ok"] is True
    user.refresh_from_db()
    assert (user.name, user.email) == ("Ирина", "i@example.com")
    assert Profile.objects.get(user=user).default_address == "ул. Старая, 1"


@pytest.mark.django_db
def test_checkout_overwrites_customer_fields_when_given(client):
    user = User.objects.create(phone="+79007776655", name="Ирина")

    client.post(
        "/api/orders/",
        data=json.dumps(_order_body(name="Ирина Новая", email="new@example.com")),
        content_type="application/json",
    )

    user.refresh_from_db()
    assert (user.name, user.email) == ("Ирина Новая", "new@example.com")


@pytest.mark.django_db
def test_checkout_links_order_to_logged_in_customer(client):
    _login(client, "+79007776655")
    user = User.objects.get()

    resp = client.post("/api/orders/", data=json.dumps(_order_body(phone="")), content_type="application/json")

    assert resp.json()["ok"] is True
    assert Order.objects.get().user == user
