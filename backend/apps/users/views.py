from rest_framework.decorators import api_view

from config.responses import ok


@api_view(["POST"])
def login(request):
    return ok()


@api_view(["POST"])
def logout(request):
    return ok()


@api_view(["GET", "PATCH"])
def me(request):
    return ok(phone="", name="", email="", default_address="")
