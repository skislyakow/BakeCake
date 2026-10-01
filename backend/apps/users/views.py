from rest_framework.decorators import api_view
from django.conf import settings
from django.contrib.auth import (
    get_user_model,
    login as auth_login,
    logout as auth_logout,
)
from config.responses import fail, ok
from .models import Profile
from .zvonok import ZvonokError, check_last_digits

User = get_user_model()


def _confirm_last4(request, phone):
    """Проверка последних 4 цифр. Возвращает текст ошибки или None."""
    last4 = str(request.data.get("last4") or "").strip()
    if len(last4) != 4 or not last4.isdigit():
        return "Введите 4 последние цифры номера"
    try:
        if not check_last_digits(phone, last4):
            return "Цифры не совпали с номером"
    except ZvonokError:
        return "Не получилось проверить номер, попробуйте позже"
    return None


@api_view(["POST"])
def login(request):
    phone = (request.data.get("phone") or "").strip()
    if not phone:
        return fail({"phone": "Введите номер телефона"})

    if settings.AUTH_MODE == "flashcall":
        error = _confirm_last4(request, phone)
        if error:
            return fail({"last4": error})

    user, _ = User.objects.get_or_create(phone=phone)
    Profile.objects.get_or_create(user=user)
    auth_login(request, user)
    return ok(
        user={
            "id": user.id,
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

    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "PATCH":
        name = request.data.get("name")
        email = request.data.get("email")
        default_address = request.data.get("default_address")

        if name is not None:
            request.user.name = name
        if email is not None:
            request.user.email = email
        request.user.save()

        if default_address is not None:
            profile.default_address = default_address
            profile.save()

    return ok(
        phone=request.user.phone,
        name=request.user.name,
        email=request.user.email,
        default_address=profile.default_address,
    )
