from datetime import date, time
from typing import Any

from .types import CakeChoice, CustomChoice, OrderDraft


def _as_time(value: Any) -> time | None:
    try:
        return time.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def _as_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def _as_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return value == 1


def parse_draft(payload: dict[str, Any] | None) -> OrderDraft:
    """Переводит тело запроса в типизированный черновик заказа (без обращения к БД)."""
    payload = payload or {}
    spec = payload.get("spec")
    spec_raw: dict[str, Any] = spec if isinstance(spec, dict) else {}

    cake_id = _as_int(payload.get("cake_id"))
    selection = CakeChoice(cake_id=cake_id) if cake_id is not None else CustomChoice(spec=spec_raw)

    return OrderDraft(
        selection=selection,
        delivery_date=_as_date(payload.get("delivery_date")),
        delivery_time=_as_time(payload.get("delivery_time")),
        delivery_date_raw=_as_str(payload.get("delivery_date")),
        delivery_time_raw=_as_str(payload.get("delivery_time")),
        promo_code=_as_str(payload.get("promo_code")),
        name=_as_str(payload.get("name")),
        phone=_as_str(payload.get("phone")),
        email=_as_str(payload.get("email")),
        address=_as_str(payload.get("address")),
        comment=_as_str(payload.get("comment")),
        courier_comment=_as_str(payload.get("courier_comment")),
        pd_consent=_as_bool(payload.get("pd_consent")),
        spec_raw=spec_raw,
    )
