from django.conf import settings

DATOCMS_API_TOKEN: str = getattr(settings, 'DATOCMS_API_TOKEN', None)
DATOCMS_API_URL: str = getattr(settings, 'DATOCMS_API_URL', None)
DATOCMS_ENVIRONMENT: str = getattr(settings, 'DATOCMS_ENVIRONMENT', None)

DATO_SYNC_WEBHOOK_EXPECTED_AUTH: str = getattr(settings, 'DATO_SYNC_WEBHOOK_EXPECTED_AUTH', None)