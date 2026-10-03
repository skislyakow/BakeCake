from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser

from config.responses import ok
from apps.analytics import stats as stats_helpers
from apps.analytics.models import Visit
from apps.orders.models import Order

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

BC_UTM_COOKIE = "bc_utm"
BC_UTM_MAX_AGE = 30 * 24 * 60 * 60


def _utm_field(request, name):
    value = ""
    if hasattr(request.data, "get"):
        value = request.data.get(name, "")
    if not value:
        value = request.query_params.get(name, "")
    return (value or "").strip()


def _first_touch(request, response, utm_source, utm_medium="", utm_campaign=""):
    if not request.COOKIES.get(BC_UTM_COOKIE) and (utm_source or utm_campaign):
        value = f"{utm_source}|{utm_medium}|{utm_campaign}"
        response.set_cookie(
            BC_UTM_COOKIE,
            value,
            max_age=BC_UTM_MAX_AGE,
            httponly=False,
            samesite="Lax",
        )
    return response


def _read_first_touch(request):
    value = request.COOKIES.get(BC_UTM_COOKIE, "") or ""
    parts = value.split("|")
    source = parts[0] if parts else ""
    medium = parts[1] if len(parts) > 1 else ""
    campaign = parts[2] if len(parts) > 2 else ""
    return source, medium, campaign


@api_view(["POST"])
def track_visit(request):
    utm_source = _utm_field(request, "utm_source")
    utm_medium = _utm_field(request, "utm_medium")
    utm_campaign = _utm_field(request, "utm_campaign")
    utm_content = _utm_field(request, "utm_content")
    utm_term = _utm_field(request, "utm_term")
    referrer = _utm_field(request, "referrer")[:500]
    landing_path = _utm_field(request, "landing_path") or "/"
    landing_path = landing_path[:300]

    if not request.session.session_key:
        request.session.create()

    user = request.user if request.user.is_authenticated else None
    Visit.objects.create(
        session_key=request.session.session_key,
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        utm_term=utm_term,
        referrer=referrer,
        landing_path=landing_path,
        user=user,
    )

    response = ok()
    return _first_touch(request, response, utm_source, utm_medium, utm_campaign)


@api_view(["GET"])
def admin_orders(request):
    return ok(items=[], total=0)


@api_view(["PATCH"])
def admin_order_patch(request, order_id):
    return ok()


def _date_params(request):
    return (
        stats_helpers.parse_date(request.GET.get("from")),
        stats_helpers.parse_date(request.GET.get("to")),
        request.GET.get("utm_source") or None,
    )


@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_stats(request):
    from_date, to_date, utm_source = _date_params(request)
    data = stats_helpers.build_stats(from_date, to_date, utm_source)
    return ok(
        orders=data["orders"],
        revenue=data["revenue"],
        avg_check=data["avg_check"],
        conversion=data["conversion"],
        visits=data["visits"],
        channels=data["channels"],
        days=data["days"],
    )


def _csv_response(filename, columns, rows):
    body_lines = [";".join(columns)]
    body_lines += [";".join(_cell(str(value)) for value in row) for row in rows]
    body = "\r\n".join(body_lines) + "\r\n"
    response = HttpResponse("\ufeff" + body, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _cell(value):
    return value.replace('"', '""')


def _orders_for_export(from_date, to_date, utm_source):
    qs = Order.objects.select_related("user")
    if from_date:
        qs = qs.filter(created__date__gte=from_date)
    if to_date:
        qs = qs.filter(created__date__lte=to_date)
    if utm_source:
        qs = qs.filter(utm_source=utm_source)
    return qs.order_by("-created")


@api_view(["GET"])
@permission_classes([IsAdminUser])
def export_orders_csv(request):
    from_date, to_date, utm_source = _date_params(request)
    rows = []
    for order in _orders_for_export(from_date, to_date, utm_source):
        rows.append(
            [
                order.number,
                order.get_status_display(),  # pyright: ignore[reportAttributeAccessIssue]
                order.delivery_date.isoformat(),
                stats_helpers.format_hhmm(order.delivery_time),
                order.total,
                "да" if order.is_rush else "нет",
                order.user.phone,
                order.address,
                order.utm_source or "прямой",
                order.utm_campaign,
                order.created.strftime("%Y-%m-%d %H:%M"),
            ]
        )
    return _csv_response("orders.csv", CSV_ORDERS_COLUMNS, rows)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def export_stats_csv(request):
    from_date, to_date, utm_source = _date_params(request)
    data = stats_helpers.build_stats(from_date, to_date, utm_source)
    rows = [
        [
            channel["source"],
            channel["visits"],
            channel["orders"],
            channel["paid"],
            channel["revenue"],
            f'{channel["conversion"]:.1f}%',
        ]
        for channel in data["channels"]
    ]
    return _csv_response("stats.csv", CSV_STATS_COLUMNS, rows)