from config.responses import ok
from django.conf import settings
from rest_framework.decorators import api_view


@api_view(["GET"])
def configurator(request):
    return ok(
        groups=[
            {
                "code": "levels",
                "title": "Количество уровней",
                "is_required": True,
                "options": [{"id": 1, "title": "1", "price_delta": 400}],
            },
            {
                "code": "berries",
                "title": "Ягоды",
                "is_required": False,
                "options": [{"id": 1, "title": "Ежевика", "price_delta": 400}],
            },
        ],
        inscription_price=settings.INSCRIPTION_PRICE,
        delivery={
            "from": settings.DELIVERY_FROM,
            "to": settings.DELIVERY_TO,
            "lead_time_hours": settings.LEAD_TIME_HOURS,
            "rush_surcharge_percent": settings.RUSH_SURCHARGE_PERCENT,
        },
    )
