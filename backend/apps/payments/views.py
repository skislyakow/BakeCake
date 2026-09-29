from rest_framework.decorators import api_view

from config.responses import ok


@api_view(["POST"])
def create_payment(request, order_id):
    return ok(confirmation_url="")


@api_view(["POST"])
def webhook(request):
    return ok()
