from time import sleep

from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from dato_sync.errors import BadConfigurationError
from dato_sync.fetcher import fetcher


@csrf_exempt
@require_POST
def sync(request: WSGIRequest) -> HttpResponse:
    """Called by dato hook to initiate a delta sync"""
    if not settings.DATO_SYNC_WEBHOOK_EXPECTED_AUTH:
        raise BadConfigurationError("DATO_SYNC_WEBHOOK_EXPECTED_AUTH not configured")

    if request.headers.get("Authorization") != settings.DATO_SYNC_WEBHOOK_EXPECTED_AUTH:
        return HttpResponse("Unauthorized", status=401)

    sleep(seconds=1) # It takes a little bit for Dato to return the new values via the API
    # TODO: use data from body
    fetcher.fetch(force_full_sync=False)
    return HttpResponse(status=204)