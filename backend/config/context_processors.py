from django.conf import settings

def jivosite(request):
    return {
        "JIVO_SITE_ID": getattr(settings, "JIVO_SITE_ID", "")
    }
