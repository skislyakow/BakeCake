from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from apps.orders.models import Order
from apps.promo.models import PromoCode


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
    actor: Any = None
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
    promo_code: str = ""
    name: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    comment: str = ""
    courier_comment: str = ""
    cake_id_raw: Any = None
    spec_raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PlacedOrder:
    order: Order
    quote: Quote
