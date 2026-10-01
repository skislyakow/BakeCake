import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.signals import connection_created
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / ".env")

DEV_SECRET_KEY = "dev-insecure-key-change-me-in-production"
SECRET_KEY = os.environ.get("SECRET_KEY", DEV_SECRET_KEY)
DEBUG = os.environ.get("DEBUG", "1") == "1"

if not DEBUG and SECRET_KEY == DEV_SECRET_KEY:
    raise ImproperlyConfigured(
        "SECRET_KEY is not set: fill it in .env before running with DEBUG=0. "
        "Generate with: python -c \"from django.core.management.utils import "
        "get_random_secret_key; print(get_random_secret_key())\""
    )
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.users",
    "apps.catalog",
    "apps.pricing",
    "apps.orders",
    "apps.payments",
    "apps.promo",
    "apps.analytics",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {"timeout": 20},
    }
}


def enable_wal(sender, connection, **kwargs):
    connection.cursor().execute("PRAGMA journal_mode=WAL;")


connection_created.connect(enable_wal)
AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = []
LOGIN_URL = "/lk/"
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
DELIVERY_FROM = "10:00"
DELIVERY_TO = "23:00"
LEAD_TIME_HOURS = 24
RUSH_SURCHARGE_PERCENT = 20
INSCRIPTION_PRICE = 500
PD_VERSION = "1.0"
SHOP_PHONE = os.environ.get("SHOP_PHONE", "8 (495) 000-00-00")
YOO_SHOP_ID = os.environ.get("YOO_SHOP_ID", "")
YOO_SECRET_KEY = os.environ.get("YOO_SECRET_KEY", "")
JIVO_SITE_ID = os.environ.get("JIVO_SITE_ID", "")

# Вход по номеру телефона. demo — любой номер создаёт пользователя (шаг 6),
# flashcall — последние 4 цифры сверяются через Звонок™ (шаг 27).
AUTH_MODE = os.environ.get("AUTH_MODE", "demo")
ZVONOK_API_KEY = os.environ.get("ZVONOK_API_KEY", "")
ZVONOK_API_SECRET = os.environ.get("ZVONOK_API_SECRET", "")
# Адрес метода Flash Call вынесен в настройку: точный путь и имена полей
# в документации Звонка не опубликованы, проверять надо по ключам аккаунта.
ZVONOK_FLASHCALL_URL = os.environ.get(
    "ZVONOK_FLASHCALL_URL", "https://api.zvonok.com/v1/verification/flashcall"
)
