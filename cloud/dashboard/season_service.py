"""Cloud replica operational season reset (mirrors local SoR semantics)."""

from __future__ import annotations

from django.utils import timezone

from replica.models import ReplicaDetectionFail, ReplicaParkingSession, Site


def apply_replica_season_reset(site: Site) -> dict:
    """
    Close parked/unpaid replica sessions as waived, delete pending fails,
    and set site.season_started_at.
    """
    now = timezone.now()
    closed_sessions = 0

    for session in ReplicaParkingSession.objects.filter(
        site=site, status__in=['parked', 'unpaid']
    ):
        if session.exit_time is None:
            session.exit_time = now
        if session.entry_time and session.exit_time:
            duration_seconds = (session.exit_time - session.entry_time).total_seconds()
            session.duration_minutes = max(0, int(duration_seconds // 60))
        session.status = 'waived'
        session.payment_method = 'waived'
        note_suffix = '[Season reset]'
        existing = (session.notes or '').strip()
        session.notes = f'{existing} {note_suffix}'.strip() if existing else note_suffix
        session.save(
            update_fields=[
                'exit_time',
                'duration_minutes',
                'status',
                'payment_method',
                'notes',
            ]
        )
        closed_sessions += 1

    deleted_fails, _ = ReplicaDetectionFail.objects.filter(
        site=site,
        review_status='pending',
    ).delete()

    site.season_started_at = now
    site.save(update_fields=['season_started_at'])

    return {
        'closed_sessions': closed_sessions,
        'deleted_detection_fails': deleted_fails,
        'season_started_at': now.isoformat(),
    }
