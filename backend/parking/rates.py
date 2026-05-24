"""
Active parking rate configuration loaded from the database.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RateSettings:
    rate_per_hour_toman: int
    daily_cap_toman: int
    grace_period_minutes: int
    student_discount_percent: int


DEFAULT_RATE_SETTINGS = RateSettings(
    rate_per_hour_toman=5000,
    daily_cap_toman=40000,
    grace_period_minutes=10,
    student_discount_percent=80,
)


def get_active_rate_settings() -> RateSettings:
    """Return the active RateConfig row, or built-in defaults if none exists."""
    try:
        from .models import RateConfig

        config: Optional[RateConfig] = (
            RateConfig.objects.filter(is_active=True).order_by('-updated_at').first()
        )
        if config is None:
            config = RateConfig.objects.order_by('-updated_at').first()
        if config is not None:
            return RateSettings(
                rate_per_hour_toman=int(config.rate_per_hour),
                daily_cap_toman=int(config.daily_cap),
                grace_period_minutes=int(config.grace_period_minutes),
                student_discount_percent=int(config.student_discount_percent),
            )
    except Exception:
        pass
    return DEFAULT_RATE_SETTINGS
