"""
Local-first cloud sync outbox.

Enqueue after local commit only. Never call cloud APIs from the gate critical path.
"""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import (
    EventMedia,
    GateEvent,
    ParkingSession,
    SyncOutbox,
    SyncState,
)

logger = logging.getLogger(__name__)

METADATA_TYPES = ('gate_event', 'parking_session', 'detection_fail', 'season_reset')
IMAGE_TYPES = ('event_media',)
MAX_ATTEMPTS = 12


def _site_id() -> str:
    return getattr(settings, 'CLOUD_SITE_ID', 'pilot-main')


def refresh_sync_state() -> SyncState:
    state = SyncState.get_singleton()
    state.pending_metadata_count = SyncOutbox.objects.filter(
        status='pending',
        payload_type__in=METADATA_TYPES,
    ).count()
    state.pending_image_count = SyncOutbox.objects.filter(
        status='pending',
        payload_type__in=IMAGE_TYPES,
    ).count()
    state.dead_letter_count = SyncOutbox.objects.filter(status='dead_letter').count()
    state.save(
        update_fields=[
            'pending_metadata_count',
            'pending_image_count',
            'dead_letter_count',
            'updated_at',
        ]
    )
    return state


def enqueue(
    *,
    payload_type: str,
    payload_uuid: uuid.UUID,
    body: Dict[str, Any],
) -> SyncOutbox:
    """Insert or refresh a pending outbox row (idempotent per type+uuid while pending)."""
    body = dict(body)
    body.setdefault('site_id', _site_id())
    existing = (
        SyncOutbox.objects.filter(
            payload_type=payload_type,
            payload_uuid=payload_uuid,
            status__in=('pending', 'sending', 'dead_letter'),
        )
        .order_by('-id')
        .first()
    )
    if existing:
        existing.body_json = body
        existing.status = 'pending'
        existing.next_attempt_at = timezone.now()
        existing.last_error = ''
        existing.save(
            update_fields=['body_json', 'status', 'next_attempt_at', 'last_error', 'updated_at']
        )
        return existing
    return SyncOutbox.objects.create(
        payload_type=payload_type,
        payload_uuid=payload_uuid,
        body_json=body,
        status='pending',
        next_attempt_at=timezone.now(),
    )


def gate_event_payload(gate_event: GateEvent, session: Optional[ParkingSession] = None) -> Dict[str, Any]:
    session_uuid = None
    if session is not None and session.session_uuid:
        session_uuid = str(session.session_uuid)
    elif gate_event.session_id:
        try:
            sess = gate_event.session
            if sess and sess.session_uuid:
                session_uuid = str(sess.session_uuid)
        except Exception:
            pass

    operator = None
    if gate_event.operator_id:
        op = gate_event.operator
        operator = {
            'id': op.id if op else gate_event.operator_id,
            'name': getattr(op, 'full_name', None) or '',
        }

    matched_user = None
    if gate_event.matched_user_id:
        u = gate_event.matched_user
        matched_user = {
            'id': u.id if u else gate_event.matched_user_id,
            'full_name': getattr(u, 'full_name', '') or '',
            'student_id': getattr(u, 'student_id', '') or '',
            'phone': getattr(u, 'phone', '') or '',
        }

    return {
        'type': 'gate_event',
        'site_id': _site_id(),
        'event_uuid': str(gate_event.event_uuid),
        'occurred_at': gate_event.created_at.isoformat() if gate_event.created_at else None,
        'direction': gate_event.direction,
        'camera_id': gate_event.camera_id,
        'plate_raw': gate_event.plate_raw,
        'plate_confirmed': gate_event.plate_confirmed,
        'confidence': float(gate_event.confidence_score) if gate_event.confidence_score is not None else None,
        'was_edited': gate_event.was_edited,
        'was_auto_approved': gate_event.was_auto_approved,
        'was_rejected': gate_event.was_rejected,
        'session_uuid': session_uuid,
        'operator': operator,
        'matched_user': matched_user,
        'local_ids': {
            'gate_event_id': gate_event.id,
            'session_id': session.id if session else gate_event.session_id,
        },
    }


def parking_session_payload(session: ParkingSession) -> Dict[str, Any]:
    plate_number = ''
    user_name = ''
    if session.plate_id:
        plate_number = session.plate.plate_number if session.plate else ''
        if session.plate and session.plate.user_id:
            user_name = getattr(session.plate.user, 'full_name', '') or ''
    else:
        plate_number = session.guest_plate_number or ''

    entry_uuid = str(session.entry_event.event_uuid) if session.entry_event_id and session.entry_event and session.entry_event.event_uuid else None
    exit_uuid = str(session.exit_event.event_uuid) if session.exit_event_id and session.exit_event and session.exit_event.event_uuid else None

    return {
        'type': 'parking_session',
        'site_id': _site_id(),
        'session_uuid': str(session.session_uuid),
        'plate_number': plate_number,
        'user_name': user_name,
        'entry_time': session.entry_time.isoformat() if session.entry_time else None,
        'exit_time': session.exit_time.isoformat() if session.exit_time else None,
        'duration_minutes': session.duration_minutes,
        'fee_charged': int(session.fee_charged or 0),
        'status': session.status,
        'payment_method': session.payment_method,
        'entry_event_uuid': entry_uuid,
        'exit_event_uuid': exit_uuid,
        'entry_camera_id': session.entry_event.camera_id if session.entry_event_id and session.entry_event else None,
        'exit_camera_id': session.exit_event.camera_id if session.exit_event_id and session.exit_event else None,
        'notes': session.notes or '',
        'local_ids': {'session_id': session.id},
    }


def event_media_payload(media: EventMedia) -> Dict[str, Any]:
    return {
        'type': 'event_media',
        'site_id': _site_id(),
        'media_uuid': str(uuid.uuid5(media.event_uuid, media.image_type)),
        'event_uuid': str(media.event_uuid),
        'session_uuid': str(media.session_uuid) if media.session_uuid else None,
        'image_type': media.image_type,
        'content_hash': media.content_hash,
        'size_bytes': media.size_bytes,
        'local_path': media.local_path,
        'captured_at': media.captured_at.isoformat() if media.captured_at else None,
    }


def enqueue_after_gate_confirm(
    gate_event_id: int,
    session_id: Optional[int] = None,
) -> None:
    """Called from transaction.on_commit — safe if cloud is down."""
    try:
        gate_event = GateEvent.objects.select_related(
            'operator', 'matched_user', 'session', 'session__plate', 'session__plate__user'
        ).get(pk=gate_event_id)
        if not gate_event.event_uuid:
            GateEvent.objects.filter(pk=gate_event_id).update(event_uuid=uuid.uuid4())
            gate_event.refresh_from_db()

        session = None
        if session_id:
            session = ParkingSession.objects.select_related(
                'plate', 'plate__user', 'entry_event', 'exit_event'
            ).filter(pk=session_id).first()
            if session and not session.session_uuid:
                ParkingSession.objects.filter(pk=session.id).update(session_uuid=uuid.uuid4())
                session.refresh_from_db()

        enqueue(
            payload_type='gate_event',
            payload_uuid=gate_event.event_uuid,
            body=gate_event_payload(gate_event, session),
        )
        if session and session.session_uuid:
            enqueue(
                payload_type='parking_session',
                payload_uuid=session.session_uuid,
                body=parking_session_payload(session),
            )
        refresh_sync_state()
    except Exception:
        logger.exception('Failed to enqueue outbox after gate confirm id=%s', gate_event_id)


def enqueue_parking_session_update(session_id: int) -> None:
    """Re-enqueue session after cash payment / waive (idempotent upsert on cloud)."""
    try:
        session = ParkingSession.objects.select_related(
            'plate', 'plate__user', 'entry_event', 'exit_event'
        ).filter(pk=session_id).first()
        if not session:
            return
        if not session.session_uuid:
            ParkingSession.objects.filter(pk=session.id).update(session_uuid=uuid.uuid4())
            session.refresh_from_db()
        enqueue(
            payload_type='parking_session',
            payload_uuid=session.session_uuid,
            body=parking_session_payload(session),
        )
        refresh_sync_state()
    except Exception:
        logger.exception('Failed to enqueue parking session update id=%s', session_id)


def enqueue_after_season_reset(
    *,
    season_started_at,
    reset_count: int,
    closed_session_ids: list,
    deleted_pending_fails: int,
) -> None:
    """Push closed sessions + a season_reset command so cloud clears pending fails."""
    try:
        closed_uuids: list[str] = []
        for sid in closed_session_ids:
            enqueue_parking_session_update(sid)
            sess = ParkingSession.objects.filter(pk=sid).only('session_uuid').first()
            if sess and sess.session_uuid:
                closed_uuids.append(str(sess.session_uuid))

        reset_uuid = uuid.uuid4()
        body = {
            'type': 'season_reset',
            'site_id': _site_id(),
            'season_started_at': (
                season_started_at.isoformat() if season_started_at else None
            ),
            'reset_count': reset_count,
            'closed_session_uuids': closed_uuids,
            'deleted_pending_fails': True,
            'deleted_pending_fail_count': int(deleted_pending_fails or 0),
        }
        enqueue(payload_type='season_reset', payload_uuid=reset_uuid, body=body)
        refresh_sync_state()
    except Exception:
        logger.exception('Failed to enqueue outbox after season reset')


def detection_fail_payload(fail) -> Dict[str, Any]:
    return {
        'type': 'detection_fail',
        'site_id': _site_id(),
        'fail_uuid': str(fail.id),
        'id': str(fail.id),
        'capture_id': str(fail.id),
        'fail_type': fail.fail_type,
        'review_status': fail.review_status,
        'camera_id': fail.camera_id,
        'direction': fail.direction,
        'raw_ocr': fail.raw_ocr or '',
        'was_corrected': fail.review_status == 'corrected',
        'label_ground_truth': getattr(fail, 'label_ground_truth', '') or '',
        'captured_at': fail.captured_at.isoformat() if fail.captured_at else None,
        'validation_error': fail.validation_error or '',
        'plate_confidence': float(fail.plate_confidence) if fail.plate_confidence is not None else None,
        'char_confidence': float(fail.char_confidence) if fail.char_confidence is not None else None,
        'has_scene_b': bool(getattr(fail, 'has_scene_b', False)),
        'local_data_path': fail.local_data_path or '',
    }


def enqueue_detection_fail(fail) -> None:
    try:
        enqueue(
            payload_type='detection_fail',
            payload_uuid=fail.id,
            body=detection_fail_payload(fail),
        )
        # Also enqueue local media files as event_media-style if present on disk via Django media
        for image_type, field_name in (
            ('fail_full', 'full_image'),
            ('fail_crop', 'crop_image'),
            ('fail_scene_b', 'scene_b_image'),
        ):
            field = getattr(fail, field_name, None)
            if not field:
                continue
            try:
                path = field.path
            except Exception:
                continue
            from pathlib import Path

            p = Path(path)
            if not p.is_file():
                continue
            media_uuid = uuid.uuid5(fail.id, image_type)
            body = {
                'type': 'event_media',
                'site_id': _site_id(),
                'media_uuid': str(media_uuid),
                'event_uuid': str(fail.id),
                'session_uuid': None,
                'image_type': image_type,
                'content_hash': '',
                'size_bytes': p.stat().st_size,
                'local_path': str(p),
                'captured_at': fail.captured_at.isoformat() if fail.captured_at else None,
                'is_detection_fail': True,
            }
            enqueue(payload_type='event_media', payload_uuid=media_uuid, body=body)
        refresh_sync_state()
    except Exception:
        logger.exception('Failed to enqueue detection fail %s', getattr(fail, 'id', None))


def enqueue_event_media(media: EventMedia) -> None:
    try:
        media_uuid = uuid.uuid5(media.event_uuid, media.image_type)
        enqueue(
            payload_type='event_media',
            payload_uuid=media_uuid,
            body=event_media_payload(media),
        )
        refresh_sync_state()
    except Exception:
        logger.exception('Failed to enqueue event media id=%s', media.id)


def mark_acked(row: SyncOutbox) -> None:
    row.status = 'acked'
    row.acked_at = timezone.now()
    row.last_error = ''
    row.save(update_fields=['status', 'acked_at', 'last_error', 'updated_at'])


def mark_retry(row: SyncOutbox, error: str) -> None:
    row.attempts += 1
    row.last_error = (error or '')[:2000]
    if row.attempts >= MAX_ATTEMPTS:
        row.status = 'dead_letter'
        row.next_attempt_at = timezone.now()
    else:
        delay = min(3600, (2 ** min(row.attempts, 10)))
        # jitter ~10%
        jitter = int(delay * 0.1 * (row.id % 7) / 7)
        row.status = 'pending'
        row.next_attempt_at = timezone.now() + timedelta(seconds=delay + jitter)
    row.save(
        update_fields=['attempts', 'last_error', 'status', 'next_attempt_at', 'updated_at']
    )
    state = SyncState.get_singleton()
    state.last_error_at = timezone.now()
    state.last_error = row.last_error
    state.save(update_fields=['last_error_at', 'last_error', 'updated_at'])


def claim_batch(limit: int = 20, *, images: bool = False):
    """Claim pending rows ready for attempt (oldest first)."""
    types = IMAGE_TYPES if images else METADATA_TYPES
    now = timezone.now()
    with transaction.atomic():
        base = SyncOutbox.objects.filter(
            status='pending', payload_type__in=types, next_attempt_at__lte=now
        ).order_by('created_at')
        try:
            qs = base.select_for_update(skip_locked=True)[:limit]
            rows = list(qs)
        except Exception:
            rows = list(base[:limit])
        for row in rows:
            row.status = 'sending'
            row.save(update_fields=['status', 'updated_at'])
        return rows


def requeue_dead_letters(ids=None) -> int:
    qs = SyncOutbox.objects.filter(status='dead_letter')
    if ids is not None:
        qs = qs.filter(id__in=ids)
    return qs.update(
        status='pending',
        next_attempt_at=timezone.now(),
        last_error='',
        attempts=0,
    )
