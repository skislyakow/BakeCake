"""Подтверждение номера звонком через Звонок™.

Провайдер работает по postback: мы инициируем проверку, человек звонит на
служебный номер, а Звонок присылает результат на наш URL. Точные имена полей
и схема подписи в публичной документации недоступны без аккаунта, поэтому
адаптер намеренно собран из настроек и разбирает несколько разумных вариантов
имён. Перед включением `AUTH_MODE=call` на проде эти места нужно сверить с
кабинетом Звонка (.agents/PLAN.md, шаг 27).
"""
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any

from django.conf import settings

SIGNATURE_PREFIX = "sha256="


class ZvonokError(Exception):
    """Провайдер недоступен или ответил ошибкой."""


class ZvonokNotConfigured(ZvonokError):
    """Нет ключей/URL — режим `call` включать нельзя."""


def is_configured() -> bool:
    return bool(
        getattr(settings, "ZVONOK_API_KEY", "")
        and getattr(settings, "ZVONOK_API_SECRET", "")
        and getattr(settings, "ZVONOK_VERIFY_URL", "")
    )


def _require_settings() -> tuple[str, str, str]:
    if not is_configured():
        raise ZvonokNotConfigured(
            "ZVONOK_API_KEY, ZVONOK_API_SECRET и ZVONOK_VERIFY_URL должны быть заданы"
        )
    return (
        settings.ZVONOK_API_KEY,
        settings.ZVONOK_API_SECRET,
        settings.ZVONOK_VERIFY_URL,
    )


def start_verification(*, phone: str, session_id: str) -> str:
    """Создаёт проверку у провайдера и возвращает его ID (если он есть)."""
    api_key, api_secret, verify_url = _require_settings()
    payload = {
        "phone": phone,
        "session_id": session_id,
        "callback_url": settings.SITE_URL.rstrip("/") + "/api/auth/verify/postback/",
    }
    request = urllib.request.Request(
        verify_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": api_key,
            "X-API-SECRET": api_secret,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(
            request, timeout=getattr(settings, "ZVONOK_TIMEOUT_SECONDS", 10)
        ) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise ZvonokError(f"Звонок вернул HTTP {error.code}") from error
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise ZvonokError(f"Звонок недоступен: {error}") from error

    if not isinstance(body, dict):
        return ""
    for key in ("id", "call_id", "verification_id", "uuid"):
        value = body.get(key)
        if value:
            return str(value)
    return ""


def signature_for(raw_body: bytes) -> str:
    """HMAC-SHA256 тела запроса; сравнение — только `hmac.compare_digest`."""
    secret = getattr(settings, "ZVONOK_API_SECRET", "")
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return SIGNATURE_PREFIX + digest


def verify_signature(raw_body: bytes, header_value: str) -> bool:
    """Проверяет подпись postback, не давая подделать подтверждение номера."""
    if not getattr(settings, "ZVONOK_API_SECRET", "") or not header_value:
        return False
    expected = signature_for(raw_body)
    provided = header_value.strip()
    if provided.lower().startswith(SIGNATURE_PREFIX):
        provided = provided[len(SIGNATURE_PREFIX) :]
    return hmac.compare_digest(expected[len(SIGNATURE_PREFIX) :], provided)


def postback_phone(payload: Mapping[str, Any]) -> str:
    for key in ("phone", "caller", "from", "number", "phone_number"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def postback_token(payload: Mapping[str, Any]) -> str:
    for key in ("session_id", "token", "custom_id", "external_id"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def postback_is_success(payload: Mapping[str, Any]) -> bool:
    for key in ("status", "event", "result", "call_status"):
        value = payload.get(key)
        if value is not None:
            return str(value).strip().lower() in {
                "confirmed",
                "success",
                "completed",
                "answered",
                "ok",
            }
    return False
