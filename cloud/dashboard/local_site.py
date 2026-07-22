"""Proxy End Season / shift reset to the local SoR site API."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


def local_season_configured() -> bool:
    return bool(getattr(settings, 'LOCAL_SITE_API_URL', '') or '')


def _post_json(url: str, payload: dict, headers: Optional[dict] = None, timeout: float = 15.0) -> Tuple[int, dict]:
    data = json.dumps(payload).encode('utf-8')
    req_headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            try:
                parsed = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = {'raw': body}
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='replace')
        try:
            parsed = json.loads(err_body) if err_body else {}
        except json.JSONDecodeError:
            parsed = {'error': err_body[:500]}
        return e.code, parsed
    except Exception as e:
        logger.warning('Local site request failed: %s', e)
        return 0, {'error': str(e)}


def reset_local_season() -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Login to local Django, then POST /api/parking/season/reset/.
    Returns (ok, message_fa, payload).
    """
    base = (getattr(settings, 'LOCAL_SITE_API_URL', '') or '').rstrip('/')
    phone = getattr(settings, 'LOCAL_SITE_OPERATOR_PHONE', '') or ''
    password = getattr(settings, 'LOCAL_SITE_OPERATOR_PASSWORD', '') or ''
    if not base:
        return False, 'پیکربندی LOCAL_SITE_API_URL لازم است', None
    if not phone or not password:
        return False, 'پیکربندی LOCAL_SITE_OPERATOR_PHONE و PASSWORD لازم است', None

    status, login_body = _post_json(
        f'{base}/api/auth/login/',
        {'phone': phone, 'password': password},
    )
    if status < 200 or status >= 300:
        return False, 'ورود به سایت محلی ناموفق بود', login_body
    token = login_body.get('access_token') or login_body.get('access')
    if not token:
        return False, 'توکن دسترسی از سایت محلی دریافت نشد', login_body

    status, reset_body = _post_json(
        f'{base}/api/parking/season/reset/',
        {},
        headers={'Authorization': f'Bearer {token}'},
    )
    if status < 200 or status >= 300:
        msg = reset_body.get('error') if isinstance(reset_body, dict) else None
        return False, msg or 'بازنشانی فصل در سایت محلی ناموفق بود', reset_body
    return True, 'فصل عملیاتی با موفقیت بازنشانی شد', reset_body
