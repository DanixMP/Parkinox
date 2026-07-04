"""
Cross-camera duplicate prevention for gate events.

When a vehicle is read at entry and the exit camera picks up the same plate
while the car is still moving into the lot, reject the opposite direction
within the cooldown window.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .models import GateEvent

CROSS_CAMERA_COOLDOWN = timedelta(minutes=2)


def cross_camera_conflict(plate_normalized: str, direction: str) -> str | None:
    """
    Return an error message if the opposite direction was confirmed recently.
    """
    if not plate_normalized:
        return None

    opposite = 'exit' if direction == 'entry' else 'entry'
    cutoff = timezone.now() - CROSS_CAMERA_COOLDOWN

    recent = (
        GateEvent.objects.filter(
            plate_confirmed=plate_normalized,
            direction=opposite,
            was_rejected=False,
            created_at__gte=cutoff,
        )
        .order_by('-created_at')
        .first()
    )

    if recent is None:
        return None

    minutes = int(CROSS_CAMERA_COOLDOWN.total_seconds() // 60)
    label = 'ورود' if opposite == 'entry' else 'خروج'
    return (
        f'این پلاک اخیراً به عنوان {label} ثبت شده است. '
        f'ثبت دوربین مقابل تا {minutes} دقیقه مجاز نیست.'
    )
