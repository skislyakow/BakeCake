"""Живой смоук приёмки заказа: повторяет запросы фронтенда по HTTP.

Запуск: python scripts/smoke_order.py http://127.0.0.1:8123
"""
import json
import re
import sys
from datetime import date, timedelta
from typing import Any

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8123"
s = requests.Session()
failures: list[str] = []


def check(name: str, condition: bool, detail: object = "") -> None:
    print(("OK   " if condition else "FAIL ") + name + ("" if condition else f" -> {detail}"))
    if not condition:
        failures.append(name)


def get_token() -> str:
    page = s.get(f"{BASE}/")
    match = re.search(r'name="csrf-token" content="([^"]+)"', page.text)
    token = match.group(1) if match else s.cookies.get("csrftoken", "")
    return token or ""


def api(
    method: str, path: str, body: dict[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json", "X-CSRFToken": s.cookies.get("csrftoken", "")}
    if body is not None:
        headers["Content-Type"] = "application/json"
    resp = s.request(
        method,
        f"{BASE}{path}",
        headers=headers,
        data=json.dumps(body) if body is not None else None,
    )
    try:
        payload: Any = resp.json()
    except ValueError:
        payload = {"_raw": resp.text[:200]}
    if not isinstance(payload, dict):
        payload = {"_raw": payload}
    return resp.status_code, payload


token = get_token()
check("страница отдаёт csrf-token", bool(token))

status, config = api("GET", "/api/configurator/")
check("GET /api/configurator/ 200 + ok", status == 200 and config.get("ok") is True, config)
groups = {g["code"]: g for g in config.get("groups", [])}
check("в конструкторе есть обязательные группы", {"levels", "form", "topping"} <= set(groups), list(groups))
options = {code: groups[code]["options"][0]["id"] for code in ("levels", "form", "topping") if groups[code]["options"]}
spec = dict(options)
spec["inscription"] = "Смоук"

status, catalog = api("GET", "/api/catalog/")
check("GET /api/catalog/ 200 + ok", status == 200 and catalog.get("ok") is True, catalog)
cakes = catalog.get("items", [])
check("каталог не пуст", bool(cakes), len(cakes))

delivery_date = (date.today() + timedelta(days=3)).isoformat()

status, quote = api(
    "POST",
    "/api/quote/",
    {"spec": spec, "delivery_date": delivery_date, "delivery_time": "15:00"},
)
check("POST /api/quote/ 200 + ok", status == 200 and quote.get("ok") is True, quote)
check("quote вернул items/subtotal/total", {"items", "subtotal", "total"} <= set(quote), list(quote))
check("в позициях есть надпись", any(i["title"] == "Надпись" for i in quote.get("items", [])), quote.get("items"))

status, quote_cake = api(
    "POST",
    "/api/quote/",
    {"cake_id": cakes[0]["id"], "delivery_date": delivery_date, "delivery_time": "15:00"},
)
check("quote по готовому торту", status == 200 and quote_cake.get("ok") is True, quote_cake)
check("цена торта совпадает с каталогом", quote_cake.get("subtotal") == cakes[0]["price"], (quote_cake, cakes[0]))

status, bad = api("POST", "/api/quote/", {"spec": spec})
check("пустой слот -> обе ошибки", status == 400 and bad.get("ok") is False and set(bad.get("errors", {})) == {"delivery_date", "delivery_time"}, (status, bad))

status, bad_format = api("POST", "/api/quote/", {"spec": spec, "delivery_date": "03.11.2026", "delivery_time": "12:00"})
check("кривая дата -> текст про формат", status == 400 and bad_format.get("errors", {}).get("delivery_date") == "Неверный формат даты, ожидается ГГГГ-ММ-ДД", (status, bad_format))

order_body: dict[str, Any] = {
    "name": "Смоук Тест",
    "phone": "+7 (900) 555-11-22",
    "email": "smoke@example.com",
    "address": "ул. Проверочная, 7",
    "delivery_date": delivery_date,
    "delivery_time": "16:00",
    "comment": "живой смоук",
    "courier_comment": "домофон 7",
    "promo_code": "",
    "spec": spec,
    "pd_consent": True,
}
status, order = api("POST", "/api/orders/", order_body)
check("POST /api/orders/ 200 + ok", status == 200 and order.get("ok") is True, order)
check("есть number/order_id/total", {"number", "order_id", "total"} <= set(order), list(order))
check('payment_url == ""', order.get("payment_url") == "", order.get("payment_url"))
number = order.get("number")

status, me = api("GET", "/api/me/")
check("после заказа сессия авторизована", status == 200 and me.get("ok") is True, me)
check("телефон в профиле нормализован", me.get("phone", "").endswith("9005551122"), me.get("phone"))

status, detail = api("GET", f"/api/orders/{number}/")
check("GET /api/orders/<номер>/ 200 + ok", status == 200 and detail.get("ok") is True, detail)
check("детали содержат spec и comment", detail.get("spec") == spec and detail.get("comment") == "живой смоук", detail)

status, listed = api("GET", "/api/orders/")
check("GET /api/orders/ содержит заказ", status == 200 and listed.get("ok") is True and any(o["number"] == number for o in listed.get("items", [])), listed)

status, issue = api("POST", f"/api/orders/{number}/issue/", {"message": "смоук-жалоба"})
check("POST /api/orders/<номер>/issue/ 200 + ok", status == 200 and issue.get("ok") is True, issue)

status, cake_order = api("POST", "/api/orders/", {**order_body, "spec": None, "cake_id": cakes[0]["id"], "delivery_time": "17:00"})
check("заказ готового торта", status == 200 and cake_order.get("ok") is True, cake_order)

status, fallback = api(
    "POST",
    "/api/orders/",
    {**order_body, "cake_id": 999999, "delivery_time": "18:00", "address": "ул. Проверочная, 8"},
)
check("несуществующий cake_id -> заказ по spec", status == 200 and fallback.get("ok") is True, fallback)
status, fallback_detail = api("GET", f"/api/orders/{fallback.get('number')}/")
check("в fallback-заказе сохранён spec", fallback_detail.get("spec") == spec, fallback_detail.get("spec"))

print()
if failures:
    print(f"ПРОВАЛЕНО: {len(failures)} -> {failures}")
    sys.exit(1)
print("ЖИВОЙ СМОУК ПРОЙДЕН")
