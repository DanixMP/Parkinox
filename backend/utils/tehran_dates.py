"""Asia/Tehran calendar-day helpers shared by reports and fail-review APIs."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

TEHRAN_TZ = ZoneInfo('Asia/Tehran')


def parse_date_param(request, *, required: bool = True, default_today: bool = False):
    """
    Parse ?date=YYYY-MM-DD.

    Returns (date_obj, error_response). One of them is None.
    When required=False and date omitted: returns today (Tehran) if default_today,
    else (None, None).
    """
    raw = request.query_params.get('date', '').strip()
    if not raw:
        if default_today:
            return timezone.now().astimezone(TEHRAN_TZ).date(), None
        if required:
            return None, Response(
                {'error': 'Query parameter "date" is required (YYYY-MM-DD)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return None, None
    try:
        requested_date = datetime.strptime(raw, '%Y-%m-%d').date()
    except ValueError:
        return None, Response(
            {'error': f'Invalid date format "{raw}". Expected YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return requested_date, None


def date_range_tehran(requested_date: date):
    """
    Return (start, end) aware datetimes for the given calendar day in Asia/Tehran.
    """
    start_tehran = datetime.combine(requested_date, time.min).replace(tzinfo=TEHRAN_TZ)
    end_tehran = datetime.combine(requested_date, time.max).replace(tzinfo=TEHRAN_TZ)
    return start_tehran, end_tehran
