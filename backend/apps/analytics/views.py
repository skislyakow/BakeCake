from django.http import HttpResponse
from rest_framework.decorators import api_view

from config.responses import ok

CSV_ORDERS_COLUMNS = [
    "Номер",
    "Статус",
    "Дата доставки",
    "Время доставки",
    "Итого",
    "Срочный",
    "Телефон",
    "Адрес",
    "Источник",
    "Кампания",
    "Создан",
]
CSV_STATS_COLUMNS = ["Источник", "Визиты", "Заказы", "Оплачено", "Выручка", "Конверсия"]


@api_view(["POST"])
def track_visit(request):
    return ok()


@api_view(["GET"])
def admin_orders(request):
    return ok(items=[], total=0)


@api_view(["PATCH"])
def admin_order_patch(request, order_id):
    return ok()


@api_view(["GET"])
def admin_stats(request):
    return ok(
        orders=0,
        revenue=0,
        avg_check=0,
        conversion=0,
        visits=0,
        channels=[],
    )


def _csv_response(filename, columns):
    body = ";".join(columns) + "\r\n"
    response = HttpResponse("﻿" + body, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@api_view(["GET"])
def export_orders_csv(request):
    return _csv_response("orders.csv", CSV_ORDERS_COLUMNS)


@api_view(["GET"])
def export_stats_csv(request):
    return _csv_response("stats.csv", CSV_STATS_COLUMNS)
