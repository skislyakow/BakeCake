from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any

from apps.orders.models import Order
from apps.promo.models import PromoCode
from apps.users.models import User


@dataclass(frozen=True)
class CakeChoice:
    cake_id: int


@dataclass(frozen=True)
class CustomChoice:
    spec: dict[str, Any]


OrderSelection = CakeChoice | CustomChoice


@dataclass(frozen=True)
class PricingRules:
    delivery_from: time
    delivery_to: time
    lead_time_hours: int
    rush_surcharge_percent: int
    inscription_price: int


@dataclass(frozen=True)
class RequestContext:
    ip: str = ""
    session_key: str = ""
    actor: User | None = None
    attribution: tuple[str, str, str] = ("", "", "")
    pd_version: str = ""
    now: datetime | None = None


@dataclass(frozen=True)
class Quote:
    items: list[dict[str, Any]]
    subtotal: int
    is_rush: bool
    rush_amount: int
    discount: int
    total: int
    promo: PromoCode | None = None
    delivery_date: date | None = None
    delivery_time: time | None = None


@dataclass(frozen=True)
class OrderDraft:
    selection: OrderSelection
    delivery_date: date | None
    delivery_time: time | None
    delivery_date_raw: str = ""
    delivery_time_raw: str = ""
    promo_code: str = ""
    name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    comment: str = ""
    courier_comment: str = ""
    spec_raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlacedOrder:
    order: Order
    quote: Quote
