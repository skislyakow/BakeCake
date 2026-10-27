from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Cake
from apps.orders.models import Order, OrderEvent
from apps.pricing.models import Option, OptionGroup
from apps.promo.models import PromoCode
from apps.users.models import Profile
from apps.users.utils import normalize_phone

from .errors import OrderIntakeError
from .types import CakeChoice, CustomChoice, PlacedOrder, PricingRules, Quote

User = get_user_model()


def _get_rules(now=None):
    return PricingRules(
        delivery_from=timezone.make_aware(datetime.combine(timezone.localdate(), __import__("datetime").time.fromisoformat(settings.DELIVERY_FROM))) if False else __import__("datetime").time.fromisoformat(settings.DELIVERY_FROM),
        delivery_to=__import__("datetime").time.fromisoformat(settings.DELIVERY_TO),
        lead_time_hours=int(settings.LEAD_TIME_HOURS),
        rush_surcharge_percent=int(settings.RUSH_SURCHARGE_PERCENT),
        inscription_price=int(settings.INSCRIPTION_PRICE),
    )


def _rules_from_settings():
    return PricingRules(
        delivery_from=__import__("datetime").time.fromisoformat(settings.DELIVERY_FROM),
        delivery_to=__import__("datetime").time.fromisoformat(settings.DELIVERY_TO),
        lead_time_hours=int(settings.LEAD_TIME_HOURS),
        rush_surcharge_percent=int(settings.RUSH_SURCHARGE_PERCENT),
        inscription_price=int(settings.INSCRIPTION_PRICE),
    )


def _price_order(draft, rules, now=None):
    if now is None:
        now = timezone.now()

    if draft.delivery_date is None:
        raise OrderIntakeError({"delivery_date": "Укажите дату доставки"})
    if draft.delivery_time is None:
        raise OrderIntakeError({"delivery_time": "Укажите время доставки"})

    delivery_t = draft.delivery_time
    delivery_d = draft.delivery_date

    if not (rules.delivery_from <= delivery_t <= rules.delivery_to):
        raise OrderIntakeError({"delivery_time": f"Доставка работает с {settings.DELIVERY_FROM} до {settings.DELIVERY_TO}"})

    if delivery_d < timezone.localdate():
        raise OrderIntakeError({"delivery_date": "Дата доставки не может быть в прошлом"})

    if isinstance(draft.selection, CakeChoice):
        try:
            cake = Cake.objects.get(pk=draft.selection.cake_id, is_active=True)
        except Cake.DoesNotExist:
            # preserve behavior: invalid cake_id falls back to spec path
            spec = getattr(draft.selection, "spec", None) or draft.spec_raw or {}
            if not isinstance(spec, dict):
                raise OrderIntakeError({"spec": "Ожидается объект вида {код группы: id опции}"})
            chosen = {code: value for code, value in spec.items() if value not in (None, "", 0)}

            groups = {g.code: g for g in OptionGroup.objects.all()}
            items = []
            errors = {}
            for code, value in chosen.items():
                if code == "inscription":
                    if not isinstance(value, str):
                        errors["inscription"] = "Надпись должна быть строкой"
                    elif value.strip():
                        items.append({"title": "Надпись", "price": rules.inscription_price})
                    continue

                group = groups.get(code)
                if not group:
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

            not_chosen = sorted(g.title for g in groups.values() if g.is_required and g.code not in chosen)
            if not_chosen:
                errors["spec"] = "Не выбрано: " + ", ".join(not_chosen)
            if errors:
                raise OrderIntakeError(errors)
        else:
            items = [{"title": cake.name, "price": cake.price, "cake": cake.id}]
    elif isinstance(draft.selection, CustomChoice):
        spec = draft.selection.spec or {}
        if not isinstance(spec, dict):
            raise OrderIntakeError({"spec": "Ожидается объект вида {код группы: id опции}"})
        chosen = {code: value for code, value in spec.items() if value not in (None, "", 0)}

        groups = {g.code: g for g in OptionGroup.objects.all()}
        items = []
        errors = {}
        for code, value in chosen.items():
            if code == "inscription":
                if not isinstance(value, str):
                    errors["inscription"] = "Надпись должна быть строкой"
                elif value.strip():
                    items.append({"title": "Надпись", "price": rules.inscription_price})
                continue

            group = groups.get(code)
            if not group:
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

        not_chosen = sorted(g.title for g in groups.values() if g.is_required and g.code not in chosen)
        if not_chosen:
            errors["spec"] = "Не выбрано: " + ", ".join(not_chosen)
        if errors:
            raise OrderIntakeError(errors)
    else:
        raise OrderIntakeError({"spec": "Ожидается объект вида {код группы: id опции}"})

    subtotal = sum(item["price"] for item in items)

    delivery_dt = timezone.make_aware(datetime.combine(delivery_d, delivery_t))
    is_rush = delivery_dt < now + timedelta(hours=rules.lead_time_hours)

    rush_amount = 0
    if is_rush:
        rush_amount = round(subtotal * rules.rush_surcharge_percent / 100)

    promo = None
    discount = 0
    code = (draft.promo_code or "").strip()
    if code:
        try:
            promo = PromoCode.objects.get(code__iexact=code, active=True)
        except PromoCode.DoesNotExist:
            raise OrderIntakeError({"promo_code": "Промокод не найден или неактивен"})
        discount = round((subtotal + rush_amount) * promo.percent / 100)

    total = subtotal + rush_amount - discount

    return Quote(
        items=items,
        subtotal=subtotal,
        is_rush=is_rush,
        rush_amount=rush_amount,
        discount=discount,
        total=total,
        promo=promo,
        delivery_date=delivery_d,
        delivery_time=delivery_t,
    )


def price_order(draft, rules=None, now=None):
    if rules is None:
        rules = _rules_from_settings()
    return _price_order(draft, rules, now)


def quote(draft, rules=None, now=None):
    q = price_order(draft, rules, now)
    return q


def place_order(draft, context, rules=None):
    if rules is None:
        rules = _rules_from_settings()

    now = context.now if getattr(context, "now", None) is not None else timezone.now()
    q = _price_order(draft, rules, now)

    phone = normalize_phone(draft.phone) or normalize_phone(getattr(context.actor, "phone", "") if getattr(context, "actor", None) else "")
    if not phone:
        raise OrderIntakeError({"phone": "Введите номер телефона"})

    attribution = getattr(context, "attribution", ("", "", "")) or ("", "", "")
    utm_source, utm_medium, utm_campaign = attribution[0], attribution[1], attribution[2]

    if getattr(q.promo, "pk", None):
        promo = q.promo
    else:
        promo = None

    from .types import CakeChoice, CustomChoice

    if isinstance(draft.selection, CakeChoice):
        spec = {"cake": draft.selection.cake_id}
    elif isinstance(draft.selection, CustomChoice):
        spec = {k: v for k, v in (draft.selection.spec or {}).items() if v not in (None, "", 0)}
    else:
        spec = {k: v for k, v in (getattr(draft.selection, "spec", None) or draft.spec_raw or {}).items() if v not in (None, "", 0)}

    address = (draft.address or "").strip()
    comment = (draft.comment or "").strip()
    courier_comment = (draft.courier_comment or "").strip()

    with transaction.atomic():
        user, _ = User.objects.get_or_create(phone=phone)
        name = (draft.name or "").strip()
        email = (draft.email or "").strip()
        if name:
            user.name = name
        if email:
            user.email = email
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        if address:
            profile.default_address = address
            profile.save()

        order = Order.objects.create(
            user=user,
            spec=spec,
            price_items=q.items,
            subtotal=q.subtotal,
            total=q.total,
            discount=q.discount,
            promo=promo,
            delivery_date=q.delivery_date,
            delivery_time=q.delivery_time,
            is_rush=q.is_rush,
            rush_amount=q.rush_amount,
            address=address,
            comment=comment,
            courier_comment=courier_comment,
            pd_consent_at=now,
            pd_consent_ip=(getattr(context, "ip", "") or ""),
            pd_version=(getattr(context, "pd_version", "") or ""),
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            session_key=(getattr(context, "session_key", "") or ""),
        )
        OrderEvent.objects.create(order=order, kind=OrderEvent.Kind.STATUS, text="Заказ создан")

    return PlacedOrder(order=order, quote=q)

