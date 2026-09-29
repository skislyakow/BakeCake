from rest_framework.decorators import api_view

from config.responses import ok


@api_view(["GET"])
def catalog(request):
    return ok(
        items=[
            {
                "id": 1,
                "name": "",
                "slug": "",
                "price": 0,
                "image": "",
                "description": "",
                "occasion": "",
            }
        ]
    )
