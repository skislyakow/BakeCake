import pytest

from apps.users.customer import CustomerData, customer_profile, edit_customer, identify_customer
from apps.users.models import Profile, User


@pytest.mark.django_db
def test_identify_creates_customer_and_profile():
    user = identify_customer("8 (900) 777-66-55")

    assert user.pk is not None
    assert user.phone == "+79007776655"
    assert Profile.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_identify_returns_same_customer_for_any_format():
    first = identify_customer("8 (900) 777-66-55")
    second = identify_customer("+7 900 777 66 55")

    assert first.pk == second.pk
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_identify_fills_only_empty_fields():
    user = identify_customer("+79007776655", CustomerData(name="Ирина", email="i@example.com", default_address="ул. А, 1"))

    same = identify_customer("+79007776655", CustomerData(name="", email="", default_address=""))

    same.refresh_from_db()
    assert same.pk == user.pk
    assert (same.name, same.email) == ("Ирина", "i@example.com")
    assert customer_profile(same).default_address == "ул. А, 1"


@pytest.mark.django_db
def test_identify_overwrites_when_value_given():
    identify_customer("+79007776655", CustomerData(name="Ирина", default_address="ул. А, 1"))

    user = identify_customer("+79007776655", CustomerData(name="Ирина Новая", default_address="ул. Б, 2"))

    assert user.name == "Ирина Новая"
    assert customer_profile(user).default_address == "ул. Б, 2"


@pytest.mark.django_db
def test_identify_creates_missing_profile():
    user = User.objects.create(phone="+79007776655")

    same = identify_customer("+79007776655")

    assert same.pk == user.pk
    assert Profile.objects.filter(user=user).exists()


def test_identify_requires_phone():
    with pytest.raises(ValueError):
        identify_customer("")


@pytest.mark.django_db
def test_edit_keeps_fields_absent_from_changes():
    user = identify_customer("+79007776655", CustomerData(name="Ирина", email="i@example.com", default_address="ул. А, 1"))

    profile = edit_customer(user, {"default_address": "ул. Б, 2"})

    user.refresh_from_db()
    assert (user.name, user.email) == ("Ирина", "i@example.com")
    assert profile.default_address == "ул. Б, 2"


@pytest.mark.django_db
def test_edit_clears_fields_with_empty_string():
    user = identify_customer("+79007776655", CustomerData(name="Ирина", email="i@example.com", default_address="ул. А, 1"))

    profile = edit_customer(user, {"name": "", "email": "", "default_address": ""})

    user.refresh_from_db()
    assert (user.name, user.email) == ("", "")
    assert profile.default_address == ""
