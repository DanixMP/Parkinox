"""
Parking fee calculation.

Uses proportional billing after a grace period, with daily cap and optional
student discount. Rates come from the active RateConfig row when Django is
available, otherwise from DEFAULT_RATE_SETTINGS.
"""

from datetime import datetime
from typing import Final, Optional

from parking.rates import DEFAULT_RATE_SETTINGS, RateSettings, get_active_rate_settings


# Backward-compatible constants (tests and legacy imports)
DEFAULT_RATES: Final[dict[str, int]] = {
    'rate_per_hour_toman': DEFAULT_RATE_SETTINGS.rate_per_hour_toman,
    'daily_cap_toman': DEFAULT_RATE_SETTINGS.daily_cap_toman,
    'grace_period_minutes': DEFAULT_RATE_SETTINGS.grace_period_minutes,
    'student_discount_percent': DEFAULT_RATE_SETTINGS.student_discount_percent,
}

RATES: Final[dict[str, int | float]] = {
    'per_hour_toman': DEFAULT_RATES['rate_per_hour_toman'],
    'daily_max_toman': DEFAULT_RATES['daily_cap_toman'],
    'grace_period_minutes': DEFAULT_RATES['grace_period_minutes'],
    'student_discount': DEFAULT_RATES['student_discount_percent'] / 100,
}


def calculate_fee(
    entry_time: datetime,
    exit_time: datetime,
    is_student: bool,
    rates: Optional[RateSettings] = None,
) -> int:
    """
    Calculate parking fee in Toman.

    Algorithm:
    1. duration_minutes = exit - entry
    2. If duration <= grace_period → 0
    3. billable_minutes = duration - grace_period
    4. charge = (billable_minutes * rate_per_hour) // 60
    5. charge = min(charge, daily_cap)
    6. If student → (charge * student_discount_percent) // 100
    """
    if exit_time < entry_time:
        raise ValueError('Exit time cannot be before entry time')

    settings = rates if rates is not None else get_active_rate_settings()

    duration_seconds = int((exit_time - entry_time).total_seconds())
    duration_minutes = duration_seconds // 60

    if duration_minutes <= settings.grace_period_minutes:
        return 0

    billable_minutes = duration_minutes - settings.grace_period_minutes
    charge = (billable_minutes * settings.rate_per_hour_toman) // 60
    charge = min(charge, settings.daily_cap_toman)

    if is_student:
        charge = (charge * settings.student_discount_percent) // 100

    return charge
