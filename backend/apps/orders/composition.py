"""Единое представление состава заказа.

`Order.spec` хранит черновик для повтора заказа, `price_items` — зафиксированные
позиции и цены. Этот модуль читает обе колонки и отдаёт один набор фактов для API,
админки и повтора.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.pricing.models import Option, OptionGroup


@dataclass(frozen=True)
class AdminLine:
    label: str
    value: str
    price: int | None = None
    indent: int = 0

    def render(self) -> str:
        prefix = "    " * self.indent
        if self.price is None:
            return f"{prefix}{self.label}"
        return f"{prefix}{self.label}: {self.value} — {self.price} ₽"


@dataclass(frozen=True)
class Composition:
    spec: dict[str, Any]
    labels: list[str]
    items: list[dict[str, Any]]
    admin_lines: list[AdminLine]


_GROUP_LABELS = {
    "levels": "Количество уровней",
    "form": "Форма торта",
    "topping": "Топпинг",
    "extra": "Дополнительно",
    "inscription": "Надпись",
}


def _item_index(items: list[dict[str, Any]]) -> dict[str, int]:
    index: dict[str, int] = {}
    for item in items:
        if isinstance(item, dict) and item.get("title"):
            index[str(item["title"])] = int(item.get("price") or 0)
    return index


def labels_from_items(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item["title"]) for item in items if isinstance(item, dict) and item.get("title")]


def _option_lookup(spec: dict[str, Any]) -> dict[int, Option]:
    ids = [value for value in spec.values() if isinstance(value, int) and not isinstance(value, bool)]
    if not ids:
        return {}
    return {
        option.pk: option
        for option in Option.objects.filter(pk__in=ids).select_related("group")
    }


def _group_lookup() -> dict[str, OptionGroup]:
    return {group.code: group for group in OptionGroup.objects.all()}


def _resolve_title(
    spec: dict[str, Any],
    code: str,
    groups: dict[str, OptionGroup],
    options: dict[int, Option],
    items: dict[str, int],
    used: set[str],
) -> tuple[str, str, int] | None:
    value = spec.get(code)
    if not value:
        return None
    group = groups.get(code)
    option = options.get(value) if isinstance(value, int) else None
    if option is not None and (group is None or option.group.pk == group.pk):
        title = option.title
    elif group is not None:
        fallback = (
            Option.objects.filter(group=group, title__in=[t for t in items if t not in used])
            .order_by("sort", "pk")
            .first()
        )
        if fallback is not None and fallback.title in items and fallback.title not in used:
            title = fallback.title
        else:
            title = f"#{value}"
    else:
        title = f"#{value}"
    used.add(title)
    group_title = group.title if group is not None else _GROUP_LABELS.get(code, code)
    return group_title, title, items.get(title, 0)


def _admin_lines(spec: dict[str, Any], raw_items: Any) -> list[AdminLine]:
    items = _item_index(raw_items if isinstance(raw_items, list) else [])
    groups = _group_lookup()
    options = _option_lookup(spec)
    used: set[str] = set()
    lines: list[AdminLine] = []

    for code in ("levels", "form", "topping"):
        resolved = _resolve_title(spec, code, groups, options, items, used)
        if resolved is None:
            continue
        group_title, title, price = resolved
        lines.append(AdminLine(label=group_title, value=title, price=price))

    extras: list[AdminLine] = []
    for code in ("berries", "decor"):
        resolved = _resolve_title(spec, code, groups, options, items, used)
        if resolved is None:
            continue
        group_title, title, price = resolved
        extras.append(AdminLine(label=group_title, value=title, price=price, indent=1))
    if extras:
        lines.append(AdminLine(label=_GROUP_LABELS["extra"], value=""))
        lines.extend(extras)

    inscription = spec.get("inscription")
    if inscription:
        lines.append(AdminLine(label=_GROUP_LABELS["inscription"], value=str(inscription), price=items.get("Надпись", 0)))

    return lines


def describe(order: Any) -> Composition:
    spec = order.spec if isinstance(getattr(order, "spec", None), dict) else {}
    raw_items = getattr(order, "price_items", None)
    items = [item for item in (raw_items or []) if isinstance(item, dict)]
    return Composition(
        spec=spec,
        labels=labels_from_items(items),
        items=items,
        admin_lines=_admin_lines(spec, raw_items),
    )
