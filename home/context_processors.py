from django.conf import settings


def site_settings(request):
    """Expose non-sensitive site configuration to templates."""
    return {
        'FASTAPI_PUBLIC_URL': settings.FASTAPI_PUBLIC_URL,
        'SUPPORT_PHONE': settings.SUPPORT_PHONE,
    }
