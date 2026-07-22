"""
Gate event confirmation and rejection processing.

Shared by the REST API and WebSocket consumer so entry/exit handling stays consistent.
"""

import logging
import threading
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib import request as urlrequest

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import GateEvent, ParkingSession
from .cross_camera_guard import CROSS_CAMERA_COOLDOWN, cross_camera_conflict
from .plate_utils import find_plate_record, normalize_plate_strict
from .services import ParkingSessionService

logger = logging.getLogger(__name__)


def _aware_event_time(occurred_at: Optional[datetime]) -> datetime:
    """Return timezone-aware event time; default to now when omitted."""
    if occurred_at is None:
        return timezone.now()
    if timezone.is_naive(occurred_at):
        return timezone.make_aware(occurred_at, timezone.get_current_timezone())
    return occurred_at


def _schedule_post_confirm_side_effects(
    *,
    gate_event_id: int,
    session_id: Optional[int],
    event_uuid: uuid.UUID,
    session_uuid: Optional[uuid.UUID],
    camera_id: str,
    direction: str,
    plate_confirmed: str,
    confidence_score: Optional[float],
    detection_event_id: Optional[str],
) -> None:
    """Register outbox + success-capture finalize after DB commit (never blocks caller)."""

    def _run():
        try:
            from .sync_outbox import enqueue_after_gate_confirm

            enqueue_after_gate_confirm(gate_event_id, session_id)
        except Exception:
            logger.exception('Outbox enqueue failed for gate_event_id=%s', gate_event_id)

        if not getattr(settings, 'SUCCESS_CAPTURE_ENABLED', True):
            return
        try:
            import json

            # Map Flutter/Django camera ids to Core buffer ids
            cam_map = {'entry': 'entry_camera', 'exit': 'exit_camera'}
            cam = cam_map.get(camera_id, camera_id)

            base = getattr(settings, 'SUCCESS_CAPTURE_FASTAPI_URL', 'http://127.0.0.1:8002').rstrip('/')
            payload = {
                'event_uuid': str(event_uuid),
                'session_uuid': str(session_uuid) if session_uuid else None,
                'gate_event_id': gate_event_id,
                'camera_id': cam,
                'direction': direction,
                'plate': plate_confirmed,
                'confidence': confidence_score,
                'detection_event_id': detection_event_id,
            }
            data = json.dumps(payload).encode('utf-8')
            req = urlrequest.Request(
                f'{base}/success-capture/finalize',
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST',
            )

            def _http():
                try:
                    with urlrequest.urlopen(req, timeout=8.0) as resp:
                        raw = resp.read()
                    try:
                        import json as _json

                        data = _json.loads(raw.decode('utf-8'))
                        meta = data.get('meta') or {}
                        if meta.get('buffer_miss'):
                            logger.warning(
                                'Success-capture buffer_miss for event_uuid=%s camera=%s plate=%s detection_event_id=%s',
                                event_uuid,
                                cam,
                                plate_confirmed,
                                detection_event_id,
                            )
                        files = meta.get('files') or {}
                        has_files = any(bool(v) for v in files.values()) if isinstance(files, dict) else False
                        if meta.get('media_dir') and not meta.get('buffer_miss') and has_files:
                            from .event_media_service import register_media_from_meta

                            register_media_from_meta(
                                meta, gate_event_id=gate_event_id
                            )
                    except Exception:
                        logger.warning(
                            'EventMedia register skipped for %s',
                            event_uuid,
                            exc_info=True,
                        )
                except Exception:
                    logger.warning(
                        'Success-capture finalize skipped/failed for %s',
                        event_uuid,
                        exc_info=True,
                    )

            threading.Thread(target=_http, daemon=True).start()
        except Exception:
            logger.warning('Success-capture schedule failed', exc_info=True)

    transaction.on_commit(_run)


@transaction.atomic
def confirm_gate_event(
    *,
    operator_id: int,
    camera_id: str,
    direction: str,
    plate_raw: str,
    plate_confirmed: str,
    confidence_score: Optional[float] = None,
    was_edited: bool = False,
    was_auto_approved: bool = False,
    plate_image_path: Optional[str] = None,
    occurred_at: Optional[datetime] = None,
    client_event_uuid: Optional[str] = None,
    detection_event_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a confirmed gate event and open or close the related parking session.

    Optional ``occurred_at`` backdates GateEvent.created_at (and thus session
    entry/exit times). Live callers omit it so behavior stays unchanged.

    Optional ``client_event_uuid`` / ``detection_event_id`` are additive sync hooks
    and do not change fee or session business logic.

    Returns a dict aligned with WebSocket gate_event.ack and REST GateEventResponse.
    """
    if direction not in ('entry', 'exit'):
        raise ValueError("Direction must be 'entry' or 'exit'")

    try:
        plate_confirmed_normalized = normalize_plate_strict(plate_confirmed)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    plate_raw_normalized = plate_confirmed_normalized
    if plate_raw and str(plate_raw).strip():
        try:
            plate_raw_normalized = (
                normalize_plate_strict(plate_raw) or plate_confirmed_normalized
            )
        except ValueError:
            # Keep unparseable OCR raw as-is for audit (e.g. fail-capture corrections)
            plate_raw_normalized = str(plate_raw).strip()[:20]

    if not plate_confirmed_normalized:
        raise ValueError('plate_confirmed is required')

    event_time = _aware_event_time(occurred_at)
    # Cross-camera guard is for live opposite-direction spam; skip for older events.
    apply_cross_camera = (
        occurred_at is None
        or event_time >= timezone.now() - CROSS_CAMERA_COOLDOWN
    )
    if apply_cross_camera:
        conflict = cross_camera_conflict(plate_confirmed_normalized, direction)
        if conflict:
            raise ValueError(conflict)

    matched_plate = find_plate_record(plate_confirmed_normalized)
    matched_user = matched_plate.user if matched_plate else None

    event_uuid_value = None
    if client_event_uuid:
        try:
            event_uuid_value = uuid.UUID(str(client_event_uuid))
        except (ValueError, TypeError):
            event_uuid_value = None

    create_kwargs = dict(
        camera_id=camera_id,
        direction=direction,
        plate_raw=plate_raw_normalized,
        plate_confirmed=plate_confirmed_normalized,
        confidence_score=(
            Decimal(str(confidence_score)) if confidence_score is not None else None
        ),
        plate_image_path=(plate_image_path or None),
        was_edited=was_edited,
        was_auto_approved=was_auto_approved,
        was_rejected=False,
        operator_id=operator_id,
        matched_user=matched_user,
        matched_plate=matched_plate,
    )
    if event_uuid_value is not None:
        create_kwargs['event_uuid'] = event_uuid_value

    gate_event = GateEvent.objects.create(**create_kwargs)
    # auto_now_add ignores create-time overrides; backdate via update when needed.
    if occurred_at is not None:
        GateEvent.objects.filter(pk=gate_event.pk).update(created_at=event_time)
        gate_event.created_at = event_time

    if not gate_event.event_uuid:
        new_uuid = uuid.uuid4()
        GateEvent.objects.filter(pk=gate_event.pk).update(event_uuid=new_uuid)
        gate_event.event_uuid = new_uuid

    session_id = None
    session_uuid_value = None
    fee = 0
    payment_status = 'none'
    wallet_balance = None
    wallet_sufficient = None

    if direction == 'entry':
        session = ParkingSessionService.create_entry_session(gate_event)
        session_id = session.id
        if not session.session_uuid:
            new_su = uuid.uuid4()
            ParkingSession.objects.filter(pk=session.id).update(session_uuid=new_su)
            session.session_uuid = new_su
        session_uuid_value = session.session_uuid
        payment_status = 'parked'
    else:
        result = ParkingSessionService.close_exit_session(gate_event)
        if result['session']:
            session = result['session']
            session_id = session.id
            if not session.session_uuid:
                new_su = uuid.uuid4()
                ParkingSession.objects.filter(pk=session.id).update(session_uuid=new_su)
                session.session_uuid = new_su
            session_uuid_value = session.session_uuid
            fee = result['fee']
            payment_status = result['payment_status']
            wallet_sufficient = result['wallet_sufficient']
            if matched_user:
                try:
                    wallet_balance = int(matched_user.wallet.balance)
                except Exception:
                    wallet_balance = None
        else:
            payment_status = 'no_session'

    matched_user_info = None
    if matched_user:
        matched_user_info = {
            'id': matched_user.id,
            'full_name': matched_user.full_name,
            'student_id': matched_user.student_id,
            'phone': matched_user.phone,
        }

    _schedule_post_confirm_side_effects(
        gate_event_id=gate_event.id,
        session_id=session_id,
        event_uuid=gate_event.event_uuid,
        session_uuid=session_uuid_value,
        camera_id=camera_id,
        direction=direction,
        plate_confirmed=plate_confirmed_normalized,
        confidence_score=float(confidence_score) if confidence_score is not None else None,
        detection_event_id=detection_event_id,
    )

    return {
        'event_id': gate_event.id,
        'gate_event_id': gate_event.id,
        'event_uuid': str(gate_event.event_uuid) if gate_event.event_uuid else None,
        'session_id': session_id,
        'session_uuid': str(session_uuid_value) if session_uuid_value else None,
        'matched_user': matched_user_info,
        'fee': fee,
        'payment_status': payment_status,
        'wallet_balance': wallet_balance,
        'wallet_sufficient': wallet_sufficient,
        'status': 'success',
    }


@transaction.atomic
def reject_gate_event(
    *,
    operator_id: int,
    camera_id: str,
    direction: str,
    plate_raw: str,
    confidence_score: Optional[float] = None,
) -> int:
    """Create a rejected gate event. Returns the new event id."""
    if direction not in ('entry', 'exit'):
        raise ValueError("Direction must be 'entry' or 'exit'")

    try:
        plate_raw_normalized = normalize_plate_strict(plate_raw) if plate_raw else None
    except ValueError:
        plate_raw_normalized = (plate_raw or '').strip() or None

    gate_event = GateEvent.objects.create(
        camera_id=camera_id,
        direction=direction,
        plate_raw=plate_raw_normalized,
        plate_confirmed=None,
        confidence_score=(
            Decimal(str(confidence_score)) if confidence_score is not None else None
        ),
        was_edited=False,
        was_auto_approved=False,
        was_rejected=True,
        operator_id=operator_id,
        matched_user=None,
        matched_plate=None,
    )
    return gate_event.id
