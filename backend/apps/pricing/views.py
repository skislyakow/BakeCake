from config.responses import ok
from django.conf import settings
from rest_framework.decorators import api_view
from .models import OptionGroup


@api_view(["GET"])
def configurator(request):
    groups = OptionGroup.objects.prefetch_related("options").order_by("sort", "id")
    group_data = []
    for group in groups:
        options = group.options.filter(is_available=True).order_by("sort", "id")
        group_data.append({
            "code": group.code,
            "title": group.title,
            "is_required": group.is_required,
            "options": [
                {
                    "id": opt.id,
                    "title": opt.title,
                    "price_delta": opt.price_delta,
                }
                for opt in options
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
