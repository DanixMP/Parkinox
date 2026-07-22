"""Ingest auth helpers — site machine token, not human dashboard login."""

from django.conf import settings
from django.http import JsonResponse


def require_site_token(view_func):
    def wrapper(request, *args, **kwargs):
        token = request.headers.get('X-Site-Ingest-Token') or request.META.get('HTTP_X_SITE_INGEST_TOKEN')
        if not token or token != settings.SITE_INGEST_TOKEN:
            return JsonResponse({'error': 'Unauthorized'}, status=401)
        site_id = (
            request.headers.get('X-Site-Id')
            or request.META.get('HTTP_X_SITE_ID')
            or request.POST.get('site_id')
            or ''
        )
        request.site_id = site_id or settings.DEFAULT_SITE_ID
        return view_func(request, *args, **kwargs)

    return wrapper
