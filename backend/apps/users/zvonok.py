import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


class ZvonokError(Exception):
    """Отделим свою ошибку от сетевых — их обработает вызывающий код."""


def check_last_digits(phone, last4):
    """Сверяет последние 4 цифры номера через Звонок™.

    Возвращает True, если цифры подошли. Ошибка сети или API поднимается
    как ZvonokError: молчаливый отказ превратил бы проверку в «не подошло».
    """
    if not settings.ZVONOK_API_KEY or not settings.ZVONOK_API_SECRET:
        raise ZvonokError("ZVONOK_API_KEY/ZVONOK_API_SECRET are not set")

    payload = json.dumps(
        {
            "phone": phone,
            "last_digits": last4,
            "api_key": settings.ZVONOK_API_KEY,
            "api_secret": settings.ZVONOK_API_SECRET,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        settings.ZVONOK_FLASHCALL_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-KEY": settings.ZVONOK_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise ZvonokError(f"Звонок вернул {error.code}") from error
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        raise ZvonokError(f"Звонок недоступен: {error}") from error

    logger.info("zvonok flashcall phone=%s ok=%s", phone, body.get("status"))
    return body.get("status") == "verified"
