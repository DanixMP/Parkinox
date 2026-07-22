"""Operational season reset and season boundary helpers."""

import datetime
import logging
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import DetectionFail, GateEvent, OperationalState, ParkingSession

logger = logging.getLogger(__name__)


def get_season_started_at():
    """Return the UTC timestamp marking the current operational season."""
    return OperationalState.get_singleton().season_started_at


def compute_live_stats() -> dict:
    """Calculate live dashboard statistics respecting the operational season."""
    tehran_tz = ZoneInfo('Asia/Tehran')
    now_tehran = datetime.datetime.now(tehran_tz)
    today_tehran = now_tehran.date()
    today_start_tehran = datetime.datetime.combine(
        today_tehran,
        datetime.time.min,
        tzinfo=tehran_tz,
    )
    today_end_tehran = datetime.datetime.combine(
        today_tehran,
        datetime.time.max,
        tzinfo=tehran_tz,
    )

    season_started_at = get_season_started_at()
    stats_since = max(today_start_tehran, season_started_at)

    entries_today = GateEvent.objects.filter(
        direction='entry',
        was_rejected=False,
        created_at__gte=stats_since,
        created_at__lte=today_end_tehran,
    ).count()

    exits_today = GateEvent.objects.filter(
        direction='exit',
        was_rejected=False,
        created_at__gte=stats_since,
        created_at__lte=today_end_tehran,
    ).count()

    currently_parked = ParkingSession.objects.filter(
        status='parked',
        entry_time__gte=season_started_at,
    ).count()

    revenue_result = ParkingSession.objects.filter(
        status__in=['completed', 'waived'],
        exit_time__gte=stats_since,
        exit_time__lte=today_end_tehran,
    ).aggregate(total=Sum('fee_charged'))

    return {
        'entries_today': entries_today,
        'exits_today': exits_today,
        'currently_parked': currently_parked,
        'revenue_today': int(revenue_result['total'] or 0),
        'capacity': getattr(settings, 'PARKING_CAPACITY', 100),
    }


def reset_operational_season(operator) -> tuple[OperationalState, int, int]:
    """
    Force-close active sessions and start a new operational season.

    Parked and unpaid sessions are closed as waived with a season-reset note.
    Pending DetectionFail rows are deleted; corrected / not_a_plate kept.
    Gate events are preserved for archive/reporting.
    """
    with transaction.atomic():
        now = timezone.now()
        closed_sessions = 0
        closed_session_ids: list[int] = []

        active_sessions = ParkingSession.objects.filter(
            status__in=['parked', 'unpaid'],
        ).select_for_update()

        for session in active_sessions:
            if session.exit_time is None:
                session.exit_time = now
            if session.entry_time and session.exit_time:
                duration_seconds = (session.exit_time - session.entry_time).total_seconds()
                session.duration_minutes = max(0, int(duration_seconds // 60))
            session.status = 'waived'
            session.payment_method = 'waived'
            if session.fee_charged is None:
                session.fee_charged = 0
            note_suffix = '[Season reset]'
            existing_notes = (session.notes or '').strip()
            session.notes = (
                f'{existing_notes} {note_suffix}'.strip()
                if existing_notes
                else note_suffix
            )
            session.save(
                update_fields=[
                    'exit_time',
                    'duration_minutes',
                    'status',
                    'payment_method',
                    'fee_charged',
                    'notes',
                ],
            )
            closed_sessions += 1
            closed_session_ids.append(session.id)

        deleted_detection_fails, _ = DetectionFail.objects.filter(
            review_status='pending',
        ).delete()

        state = OperationalState.get_singleton()
        state.season_started_at = now
        state.last_reset_at = now
        state.reset_count += 1
        state.last_reset_by = operator
        state.save(
            update_fields=[
                'season_started_at',
                'last_reset_at',
                'reset_count',
                'last_reset_by',
            ],
        )

        season_started_at = state.season_started_at
        reset_count = state.reset_count
        deleted_count = deleted_detection_fails
        session_ids = list(closed_session_ids)

    # Enqueue AFTER the atomic block commits so cloud sync always sees SoR changes.
    # (Avoid relying solely on on_commit under long-lived Daphne workers.)
    try:
        from .sync_outbox import enqueue_after_season_reset

        enqueue_after_season_reset(
            season_started_at=season_started_at,
            reset_count=reset_count,
            closed_session_ids=session_ids,
            deleted_pending_fails=deleted_count,
        )
    except Exception:
        logger.exception('Outbox enqueue after season reset failed')

    return state, closed_sessions, deleted_detection_fails
