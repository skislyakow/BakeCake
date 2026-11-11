import json
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import (
    login as auth_login,
    logout as auth_logout,
)
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from rest_framework import status as http_status
from rest_framework.decorators import api_view

from config.responses import fail, ok
from . import zvonok
from .customer import customer_profile, edit_customer, identify_customer, record_consent
from .models import PhoneConfirm
from .utils import normalize_phone, request_ip

logger = logging.getLogger(__name__)


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return value == 1


def _user_payload(user) -> dict:
    return {
        "id": user.pk,
        "phone": user.phone,
        "name": user.name,
        "email": user.email,
    }


def _record_consent_if_checked(request, user) -> None:
    if _truthy(request.data.get("consent_pdp")):
        record_consent(
            user,
            ip=request_ip(request),
            version=getattr(settings, "PD_VERSION", ""),
        )


def _start_call_confirmation(request, phone: str):
    now = timezone.now()
    ttl = getattr(settings, "PHONE_CONFIRM_TTL_MINUTES", 5)
    max_pending = getattr(settings, "PHONE_CONFIRM_MAX_PENDING", 3)
    max_per_hour = getattr(settings, "PHONE_CONFIRM_MAX_PER_HOUR", 10)

    pending = PhoneConfirm.objects.filter(
        phone=phone,
        status=PhoneConfirm.Status.PENDING,
        expires_at__gt=now,
    ).count()
    if pending >= max_pending:
        return fail(
            {"phone": "Слишком много попыток подтверждения, попробуйте позже"},
            status=http_status.HTTP_429_TOO_MANY_REQUESTS,
        )

    recent = PhoneConfirm.objects.filter(
        phone=phone, created__gte=now - timedelta(hours=1)
    ).count()
    if recent >= max_per_hour:
        return fail(
            {"phone": "Слишком много попыток подтверждения, попробуйте позже"},
            status=http_status.HTTP_429_TOO_MANY_REQUESTS,
        )

    user = identify_customer(phone)
    _record_consent_if_checked(request, user)

    record = PhoneConfirm.objects.create(
        phone=phone,
        expires_at=now + timedelta(minutes=ttl),
    )
    try:
        zvonok_id = zvonok.start_verification(
            phone=phone, session_id=str(record.token)
        )
    except zvonok.ZvonokNotConfigured:
        record.status = PhoneConfirm.Status.REJECTED
        record.save(update_fields=["status", "updated"])
        logger.warning("zvonok is not configured, AUTH_MODE=call cannot work")
        return fail(
            {"auth": "Подтверждение звонком не настроено"},
            status=http_status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except zvonok.ZvonokError as error:
        record.status = PhoneConfirm.Status.REJECTED
        record.save(update_fields=["status", "updated"])
        logger.warning("zvonok start failed for %s: %s", phone, error)
        return fail(
            {"auth": "Не удалось инициировать звонок, попробуйте позже"},
            status=http_status.HTTP_502_BAD_GATEWAY,
        )

    if zvonok_id:
        record.zvonok_id = zvonok_id
        record.save(update_fields=["zvonok_id", "updated"])

    return ok(
        status="pending",
        token=str(record.token),
        number=getattr(settings, "ZVONOK_VERIFY_NUMBER", ""),
        expires_in=ttl * 60,
    )


@api_view(["POST"])
def login(request):
    phone = normalize_phone(request.data.get("phone"))
    if not phone:
        return fail({"phone": "Введите номер телефона"})

    mode = getattr(settings, "AUTH_MODE", "demo")
    if mode == "off":
        return fail(
            {"auth": "Вход через сайт временно отключён"},
            status=http_status.HTTP_403_FORBIDDEN,
        )
    if mode == "call":
        return _start_call_confirmation(request, phone)

    user = identify_customer(phone)
    _record_consent_if_checked(request, user)
    auth_login(request, user)
    return ok(user=_user_payload(user))


@api_view(["POST"])
def logout(request):
    if not request.user.is_authenticated:
        return fail({"auth": "Не авторизован"}, status=http_status.HTTP_401_UNAUTHORIZED)
    auth_logout(request)
    return ok()


@api_view(["GET", "PATCH"])
def me(request):
    if not request.user.is_authenticated:
        return fail({"auth": "Не авторизован"}, status=http_status.HTTP_401_UNAUTHORIZED)

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


def _call_mode_or_404():
    if getattr(settings, "AUTH_MODE", "demo") != "call":
        raise Http404


def _json(payload, status=200):
    return JsonResponse(payload, status=status)


def _json_fail(errors, status=400):
    return _json({"ok": False, "errors": errors}, status=status)


def _status_payload(record, *, user=None):
    payload = {
        "status": record.status,
        "expires_in": max(0, int((record.expires_at - timezone.now()).total_seconds())),
    }
    if user is not None:
        payload["user"] = _user_payload(user)
    return payload


@require_GET
def verify_status(request):
    _call_mode_or_404()
    token = (request.GET.get("token") or "").strip()
    if not token:
        return _json_fail({"token": "Не указан токен подтверждения"})
    try:
        record = PhoneConfirm.objects.get(token=token)
    except (PhoneConfirm.DoesNotExist, ValidationError, ValueError):
        return _json_fail(
            {"token": "Подтверждение не найдено"},
            status=http_status.HTTP_404_NOT_FOUND,
        )

    record.expire_if_needed()
    if record.status == PhoneConfirm.Status.PENDING:
        return _json({"ok": True, **_status_payload(record)})
    if record.status != PhoneConfirm.Status.CONFIRMED:
        return _json({"ok": True, **_status_payload(record)})

    with transaction.atomic():
        record = PhoneConfirm.objects.select_for_update().get(pk=record.pk)
        user = identify_customer(record.phone)
        if not record.session_issued:
            auth_login(request, user)
            record.session_issued = True
            record.save(update_fields=["session_issued", "updated"])
    return _json({"ok": True, **_status_payload(record, user=user)})


@csrf_exempt
@require_POST
def verify_postback(request):
    _call_mode_or_404()
    raw_body = request.body
    header_name = getattr(settings, "ZVONOK_SIGNATURE_HEADER", "X-Zvonok-Signature")
    signature = request.headers.get(header_name, "")
    if not zvonok.verify_signature(raw_body, signature):
        return _json_fail(
            {"signature": "Неверная подпись"},
            status=http_status.HTTP_403_FORBIDDEN,
        )

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _json_fail({"payload": "Ожидается JSON"}, status=http_status.HTTP_400_BAD_REQUEST)
    if not isinstance(payload, dict):
        return _json_fail({"payload": "Ожидается JSON-объект"}, status=http_status.HTTP_400_BAD_REQUEST)

    phone = normalize_phone(zvonok.postback_phone(payload))
    token = zvonok.postback_token(payload)
    if not phone and not token:
        return _json_fail(
            {"payload": "Нет номера или токена"},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    records = PhoneConfirm.objects.filter(status=PhoneConfirm.Status.PENDING)
    if token:
        try:
            token_uuid = uuid.UUID(token)
        except (ValidationError, ValueError, AttributeError):
            return _json({"ok": True})
        records = records.filter(token=token_uuid)
    if phone:
        records = records.filter(phone=phone)
    record = records.order_by("-created").first()
    if record is None:
        # Повторный postback или неизвестный токен: подтверждение уже не нужно.
        return _json({"ok": True})

    if record.expire_if_needed():
        return _json({"ok": True})
    if record.status != PhoneConfirm.Status.PENDING:
        return _json({"ok": True})

    if not zvonok.postback_is_success(payload):
        record.status = PhoneConfirm.Status.REJECTED
        record.attempts += 1
        record.save(update_fields=["status", "attempts", "updated"])
        return _json({"ok": True})

    record.status = PhoneConfirm.Status.CONFIRMED
    record.attempts += 1
    provider_id = payload.get("id") or payload.get("call_id")
    if provider_id:
        record.zvonok_id = str(provider_id)[:100]
    record.save(update_fields=["status", "attempts", "zvonok_id", "updated"])
    return _json({"ok": True})
