import json

import pytest
from django.urls import reverse

from apps.users.customer import identify_customer
from apps.users.models import User
from apps.users.utils import normalize_phone

CANONICAL = "+79090000000"

SAME_NUMBER_FORMATS = [
    "8 (909) 000-00-00",
    "89090000000",
    "+7 909 000-00-00",
    "7 909 000 00 00",
    "9090000000",
]


@pytest.mark.parametrize("raw", SAME_NUMBER_FORMATS)
def test_normalize_phone_reduces_formats_to_canonical(raw):
    assert normalize_phone(raw) == CANONICAL


def test_normalize_phone_keeps_unknown_value_as_is():
    assert normalize_phone("12345") == "12345"
    assert normalize_phone("") == ""
    assert normalize_phone(None) == ""


@pytest.mark.django_db
def test_manager_create_user_normalizes_phone():
    user = User.objects.create_user(phone="8 (909) 000-00-00")

    assert user.phone == CANONICAL
    assert User.objects.filter(phone=CANONICAL).exists()


@pytest.mark.django_db
def test_objects_create_normalizes_phone():
    user = User.objects.create(phone="8 (909) 000-00-00")

    assert user.phone == CANONICAL


@pytest.mark.django_db
def test_save_normalizes_phone_edited_in_admin():
    user = User.objects.create(phone="+79090000001")

    user.phone = "8 (909) 000-00-02"
    user.save()
    user.refresh_from_db()

    assert user.phone == "+79090000002"


@pytest.mark.django_db
def test_identify_customer_matches_every_format():
    first = identify_customer(SAME_NUMBER_FORMATS[0])

    for raw in SAME_NUMBER_FORMATS[1:]:
        assert identify_customer(raw).pk == first.pk

    assert User.objects.count() == 1
    assert User.objects.filter(phone=CANONICAL).exists()


@pytest.mark.django_db
def test_login_matches_every_format(client):
    for raw in SAME_NUMBER_FORMATS:
        resp = client.post(
            "/api/auth/login/",
            data=json.dumps({"phone": raw}),
            content_type="application/json",
        )
        assert resp.json()["ok"] is True

    assert User.objects.count() == 1


def _admin_user():
    return User.objects.create_superuser(phone="+79090000009", password="secret-pass-123")


def _add_user_data(phone, name):
    return {
        "phone": phone,
        "name": name,
        "password1": "secret-pass-123",
        "password2": "secret-pass-123",
    }


@pytest.mark.django_db
def test_admin_add_form_stores_canonical_phone(client):
    client.force_login(_admin_user())

    resp = client.post(reverse("admin:users_user_add"), data=_add_user_data("8 (909) 000-00-01", "Новый"))

    assert resp.status_code == 302
    assert User.objects.filter(phone="+79090000001", name="Новый").exists()


@pytest.mark.django_db
def test_admin_add_form_blocks_duplicate_in_another_format(client):
    User.objects.create(phone=CANONICAL)
    client.force_login(_admin_user())

    resp = client.post(reverse("admin:users_user_add"), data=_add_user_data("8 (909) 000-00-00", "Дубль"))

    assert resp.status_code == 200
    assert not User.objects.filter(name="Дубль").exists()
    assert User.objects.count() == 2
