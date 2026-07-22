"""Jalali (Shamsi) helpers matching Flutter toolbar format yyyy/MM/dd with Persian digits."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import jdatetime
from django.utils import timezone

TEHRAN = ZoneInfo('Asia/Tehran')

_PERSIAN_DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
_LATIN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


def to_persian_digits(s: str) -> str:
    return str(s).translate(_PERSIAN_DIGITS)


def to_latin_digits(s: str) -> str:
    return str(s).translate(_LATIN_DIGITS)


def to_jalali_str(dt, *, with_time: bool = False) -> str:
    """Format like Flutter: ۱۴۰۴/۰۴/۳۰ or ۱۴۰۴/۰۴/۳۰ ۱۴:۳۰"""
    if dt is None:
        return '—'
    if isinstance(dt, datetime):
        if timezone.is_aware(dt):
            local = timezone.localtime(dt, TEHRAN)
        else:
            local = timezone.make_aware(dt, TEHRAN)
    elif isinstance(dt, date):
        local = datetime.combine(dt, time.min, tzinfo=TEHRAN)
    else:
        return '—'
    j = jdatetime.datetime.fromgregorian(datetime=local)
    date_part = f'{j.year:04d}/{j.month:02d}/{j.day:02d}'
    if with_time:
        date_part = f'{date_part} {local.hour:02d}:{local.minute:02d}'
    return to_persian_digits(date_part)


def parse_jalali_date(value: str):
    """
    Parse Jalali yyyy/MM/dd (Persian or Latin digits) → (start_utc, end_utc) for that Tehran day.
    Returns (None, None) if empty/invalid.
    """
    if not value or not str(value).strip():
        return None, None
    raw = to_latin_digits(str(value).strip()).replace('-', '/')
    parts = [p for p in raw.split('/') if p]
    if len(parts) != 3:
        return None, None
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        j = jdatetime.date(y, m, d)
        g = j.togregorian()
        start_local = datetime(g.year, g.month, g.day, 0, 0, 0, tzinfo=TEHRAN)
        end_local = start_local + timedelta(days=1)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)
    except Exception:
        return None, None
