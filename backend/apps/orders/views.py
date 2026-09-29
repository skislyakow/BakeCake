from rest_framework.decorators import api_view

from config.responses import ok


@api_view(["POST"])
def quote(request):
    return ok(
        items=[
            {"title": "2 уровня", "price": 750},
            {"title": "Круг", "price": 400},
            {"title": "Карамельный сироп", "price": 180},
            {"title": "Ежевика", "price": 400},
            {"title": "Безе", "price": 400},
            {"title": "Надпись", "price": 500},
        ],
        subtotal=2630,
        is_rush=False,
        rush_amount=0,
        discount=263,
        total=2367,
    )


def _created_order_response():
    return ok(number="2239400223", total=2367, is_rush=False, payment_url="")


def _order_list_response():
    return ok(items=[])


@api_view(["GET", "POST"])
def orders(request):
    if request.method == "POST":
        return _created_order_response()
    return _order_list_response()


@api_view(["GET"])
def order_detail(request, number):
    return ok(
        number=str(number),
        status="paid",
        status_label="Оплачен",
        spec={},
        spec_labels=[],
        total=2367,
        delivery_date="2026-10-05",
        delivery_time="12:00",
        is_rush=False,
        is_rescheduled=True,
        reschedule_note="Новые сроки: 16:00",
        comment="",
        courier_comment="звонить за час",
    )


@api_view(["POST"])
def order_issue(request, number):
    return ok()
