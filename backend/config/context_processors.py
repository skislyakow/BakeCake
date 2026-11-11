from django.conf import settings


def jivosite(request):
    return {
        "JIVO_SITE_ID": getattr(settings, "JIVO_SITE_ID", "")
    }


def auth_mode(request):
    return {
        "AUTH_MODE": getattr(settings, "AUTH_MODE", "demo")
    }
