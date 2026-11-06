from collections.abc import Mapping
from dataclasses import dataclass

from django.db import transaction

from .models import Profile, User
from .utils import normalize_phone


@dataclass(frozen=True)
class CustomerData:
    """Данные покупателя, которые пришли вместе с заказом или из формы профиля."""

    name: str = ""
    email: str = ""
    default_address: str = ""


def customer_profile(user: User) -> Profile:
    """Профиль покупателя; создаёт его, если у старой записи его не было."""
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def identify_customer(phone: str, data: CustomerData | None = None) -> User:
    """Возвращает покупателя по номеру, создавая его и профиль при первом обращении.

    Заполняет только пустые поля: случайно пустое поле из формы заказа не должно
    стирать то, что человек уже указал в профиле.
    """
    phone = normalize_phone(phone)
    if not phone:
        raise ValueError("Телефон обязателен: identify_customer(phone)")

    with transaction.atomic():
        user, _ = User.objects.get_or_create(phone=phone)
        profile = customer_profile(user)

        if data is not None:
            changed = []
            if data.name and data.name != user.name:
                user.name = data.name
                changed.append("name")
            if data.email and data.email != user.email:
                user.email = data.email
                changed.append("email")
            if changed:
                user.save(update_fields=changed)
            if data.default_address and data.default_address != profile.default_address:
                profile.default_address = data.default_address
                profile.save(update_fields=["default_address"])

    return user


def edit_customer(user: User, changes: Mapping[str, object]) -> Profile:
    """Правит профиль из формы: `None` — поле не трогали, пустая строка — очистить."""
    profile, _ = Profile.objects.get_or_create(user=user)

    changed_user = []
    for field in ("name", "email"):
        value = changes.get(field)
        if value is None:
            continue
        setattr(user, field, str(value))
        changed_user.append(field)
    if changed_user:
        user.save(update_fields=changed_user)

    address = changes.get("default_address")
    if address is not None:
        profile.default_address = str(address)
        profile.save(update_fields=["default_address"])

    return profile
