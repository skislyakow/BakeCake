from config.responses import ok
from django.conf import settings
from rest_framework.decorators import api_view

from .models import Option, OptionGroup


@api_view(["GET"])
def configurator(request):
    options_by_group: dict[int, list[Option]] = {}
    for option in Option.objects.filter(is_available=True).select_related("group").order_by("sort", "id"):
        options_by_group.setdefault(option.group.pk, []).append(option)

    group_data = []
    for group in OptionGroup.objects.order_by("sort", "id"):
        group_data.append({
            "code": group.code,
            "title": group.title,
            "is_required": group.is_required,
            "options": [
                {
                    "id": option.pk,
                    "title": option.title,
                    "price_delta": option.price_delta,
                    "preview_key": option.preview_key,
                }
                for option in options_by_group.get(group.pk, [])
            ],
        })
    return ok(
        groups=group_data,
        inscription_price=settings.INSCRIPTION_PRICE,
        delivery={
            "from": settings.DELIVERY_FROM,
            "to": settings.DELIVERY_TO,
            "lead_time_hours": settings.LEAD_TIME_HOURS,
            "rush_surcharge_percent": settings.RUSH_SURCHARGE_PERCENT,
        },
    )
