from rest_framework.decorators import api_view
from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
)
from config.responses import fail, ok
from .customer import customer_profile, edit_customer, identify_customer
from .utils import normalize_phone


@api_view(["POST"])
def login(request):
    phone = normalize_phone(request.data.get("phone"))
    if not phone:
        return fail({"phone": "Введите номер телефона"})
    user = identify_customer(phone)
    auth_login(request, user)
    return ok(
        user={
            "id": user.pk,
            "phone": user.phone,
            "name": user.name,
            "email": user.email,
        }
    )


@api_view(["POST"])
def logout(request):
    if not request.user.is_authenticated:
        return fail({"auth": "Не авторизован"})
    auth_logout(request)
    return ok()


@api_view(["GET", "PATCH"])
def me(request):
    if not request.user.is_authenticated:
        return fail({"auth": "Не авторизован"})

    if request.method == "PATCH":
        profile = edit_customer(request.user, request.data)
    else:
        profile = customer_profile(request.user)

    return ok(
        phone=request.user.phone,
        name=request.user.name,
        email=request.user.email,
        default_address=profile.default_address,
    )
