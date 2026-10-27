from datetime import date, time

from apps.catalog.models import Cake

from .types import OrderDraft, CakeChoice, CustomChoice


def _as_time(value):
    try:
        return time.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def _as_date(value):
    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def parse_draft(payload):
    payload = payload or {}
    cake_id_raw = payload.get("cake_id")
    spec = payload.get("spec") or {}

    # keep behavior: invalid/inactive cake_id falls back to spec path
    cake_id = None
    if cake_id_raw not in (None, "",):
        try:
            cake_id = int(cake_id_raw)
        except (TypeError, ValueError):
            cake_id = None

    if cake_id is not None:
        try:
            Cake.objects.get(pk=cake_id, is_active=True)
            selection = CakeChoice(cake_id=cake_id)
        except Cake.DoesNotExist:
            selection = CustomChoice(spec=spec if isinstance(spec, dict) else {})
    else:
        selection = CustomChoice(spec=spec if isinstance(spec, dict) else {})

    return OrderDraft(
        selection=selection,
        delivery_date=_as_date(payload.get("delivery_date")),
        delivery_time=_as_time(payload.get("delivery_time")),
        promo_code=(payload.get("promo_code") or "").strip(),
        name=(payload.get("name") or "").strip(),
        phone=(payload.get("phone") or "").strip(),
        email=(payload.get("email") or "").strip(),
        address=(payload.get("address") or "").strip(),
        comment=(payload.get("comment") or "").strip(),
        courier_comment=(payload.get("courier_comment") or "").strip(),
        cake_id_raw=cake_id_raw,
        spec_raw=spec if isinstance(spec, dict) else {},
    )
