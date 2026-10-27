from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.signals import connection_created
from environs import Env, EnvError

BASE_DIR = Path(__file__).resolve().parent.parent

env = Env()
env.read_env(BASE_DIR.parent / ".env")

SECRET_KEY_ERROR = (
    "SECRET_KEY is required: add it to .env or the environment. Generate with: "
    "python -c \"from django.core.management.utils import "
    "get_random_secret_key; print(get_random_secret_key())\""
)
try:
    SECRET_KEY = env.str("SECRET_KEY")
except EnvError as exc:
    raise ImproperlyConfigured(SECRET_KEY_ERROR) from exc
if not SECRET_KEY.strip():
    raise ImproperlyConfigured(SECRET_KEY_ERROR)


def env_bool(name: str, default: bool = False) -> bool:
    """Treat an empty environment variable as unset, otherwise parse it strictly."""
    if not env.str(name, "").strip():
        return default
    return env.bool(name)


DEBUG = env_bool("DEBUG")
ALLOWED_HOSTS = [
    host.strip()
    for host in env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
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
                "config.context_processors.jivosite",
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
AUTHENTICATION_BACKENDS = ["apps.users.backends.PhoneBackend"]
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
SHOP_PHONE = env.str("SHOP_PHONE", "8 (495) 000-00-00")
YOO_SHOP_ID = env.str("YOO_SHOP_ID", "")
YOO_SECRET_KEY = env.str("YOO_SECRET_KEY", "")
SITE_URL = env.str("SITE_URL", "https://bakecake.kislyakov.pro")
JIVO_SITE_ID = env.str("JIVO_SITE_ID", "")
