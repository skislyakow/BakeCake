from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from .models import Profile, User
from .utils import normalize_phone


@dataclass(frozen=True)
class CustomerData:
    name: str = ""
    email: str = ""
    default_address: str = ""


def customer_profile(user: User) -> Profile:
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def identify_customer(phone: str, data: CustomerData | None = None) -> User:
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


def record_consent(
    user: User,
    *,
    ip: str = "",
    version: str = "",
    now: datetime | None = None,
) -> Profile:
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.consent_pdp_at = now or timezone.now()
    profile.consent_pdp_ip = ip or None
    profile.pd_version = version
    profile.save(update_fields=["consent_pdp_at", "consent_pdp_ip", "pd_version"])
    return profile


def edit_customer(user: User, changes: Mapping[str, object]) -> Profile:
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
