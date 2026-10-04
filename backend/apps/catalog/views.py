from django.templatetags.static import static
from rest_framework.decorators import api_view

from config.responses import ok
from .models import Cake


@api_view(["GET"])
def catalog(request):
    """Каталог готовых тортов: только активные, сортировка по поводу и порядку."""
    cakes = (
        Cake.objects.filter(is_active=True)
        .order_by("occasion", "sort", "id")
        .values("id", "name", "slug", "price", "image", "description", "occasion")
    )
    items = [
        {
            "id": cake["id"],
            "name": cake["name"],
            "slug": cake["slug"],
            "price": cake["price"],
            "image_url": static(cake["image"]) if cake["image"] else "",
            "description": cake["description"],
            "occasion": cake["occasion"],
        }
        for cake in cakes
    ]
    return ok(items=items)