"""
Operator review of failed detections.

Corrected plates reuse confirm_gate_event() — no parallel parking logic.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from .gate_event_service import confirm_gate_event
from .models import DetectionFail
from .plate_utils import find_active_parked_session, find_plate_record, normalize_plate_strict

logger = logging.getLogger(__name__)


def _normalize_camera_id(camera_id: str) -> str:
    """Map FastAPI WS ids (entry_camera) to GateEvent style (entry)."""
    cid = (camera_id or '').strip().lower()
    if cid in ('entry', 'entry_camera'):
        return 'entry'
    if cid in ('exit', 'exit_camera'):
        return 'exit'
    if 'exit' in cid:
        return 'exit'
    return 'entry'


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _preflight_historical_conflicts(
    *,
    direction: str,
    plate_confirmed: str,
    occurred_at: Optional[datetime],
) -> None:
    """
    Reject delayed corrections that would corrupt live session state.

    Leaves the DetectionFail pending (caller raises before confirm).
    """
    if occurred_at is None:
        return

    try:
        plate_norm = normalize_plate_strict(plate_confirmed)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    matched_plate = find_plate_record(plate_norm)
    active = find_active_parked_session(
        plate_norm,
        matched_plate=matched_plate,
    )
    if active is None:
        return

    entry_time = _aware(active.entry_time)
    if entry_time is None:
        return

    if direction == 'exit' and entry_time > occurred_at:
        raise ValueError(
            'زمان خروج از زمان ورود جلسه فعال جدیدتر نیست؛ '
            'اصلاح با زمان اصلی تصویر ممکن نیست.'
        )

    if direction == 'entry' and entry_time >= occurred_at:
        raise ValueError(
            'برای این پلاک جلسه پارک فعال جدیدتری وجود دارد؛ '
            'اصلاح تأخیری ورود ثبت نمی‌شود.'
        )


@transaction.atomic
def review_correct(
    *,
    detection_fail: DetectionFail,
    operator_id: int,
    plate_confirmed: str,
) -> Dict[str, Any]:
    """
    Accept operator-corrected plate: create GateEvent + session via shared service,
    then link the DetectionFail record.

    Uses DetectionFail.captured_at as the gate/session event time when present.
    reviewed_at remains the operator review time.
    """
    if detection_fail.review_status != 'pending':
        raise ValueError('Detection fail already reviewed')

    camera_id = _normalize_camera_id(detection_fail.camera_id)
    direction = detection_fail.direction or (
        'exit' if camera_id == 'exit' else 'entry'
    )

    confidence = None
    if detection_fail.plate_confidence is not None:
        confidence = float(detection_fail.plate_confidence)

    image_path = ''
    if detection_fail.crop_image:
        image_path = detection_fail.crop_image.name
    elif detection_fail.full_image:
        image_path = detection_fail.full_image.name

    occurred_at = _aware(detection_fail.captured_at)
    _preflight_historical_conflicts(
        direction=direction,
        plate_confirmed=plate_confirmed,
        occurred_at=occurred_at,
    )

    result = confirm_gate_event(
        operator_id=operator_id,
        camera_id=camera_id,
        direction=direction,
        plate_raw=detection_fail.raw_ocr or '',
        plate_confirmed=plate_confirmed,
        confidence_score=confidence,
        was_edited=True,
        was_auto_approved=False,
        plate_image_path=image_path or None,
        occurred_at=occurred_at,
    )

    gate_event_id = result.get('gate_event_id') or result.get('event_id')
    detection_fail.review_status = 'corrected'
    detection_fail.not_a_plate = False
    detection_fail.label_ground_truth = plate_confirmed.strip()
    detection_fail.reviewed_by_id = operator_id
    detection_fail.reviewed_at = timezone.now()
    detection_fail.gate_event_id = gate_event_id
    detection_fail.save(
        update_fields=[
            'review_status',
            'not_a_plate',
            'label_ground_truth',
            'reviewed_by',
            'reviewed_at',
            'gate_event',
        ]
    )

    fail_id = detection_fail.id

    def _enqueue():
        try:
            from .sync_outbox import enqueue_detection_fail
            from .models import DetectionFail

            fail = DetectionFail.objects.filter(pk=fail_id).first()
            if fail:
                enqueue_detection_fail(fail)
        except Exception:
            logger.exception('Outbox enqueue after fail correct failed %s', fail_id)

    transaction.on_commit(_enqueue)

    logger.info(
        'DetectionFail %s corrected → GateEvent %s by operator %s',
        detection_fail.id,
        gate_event_id,
        operator_id,
    )
    return {
        **result,
        'detection_fail_id': str(detection_fail.id),
        'review_status': detection_fail.review_status,
    }


@transaction.atomic
def review_not_a_plate(
    *,
    detection_fail: DetectionFail,
    operator_id: int,
) -> Dict[str, Any]:
    """Mark sample as negative training data; do not create parking records."""
    if detection_fail.review_status != 'pending':
        raise ValueError('Detection fail already reviewed')

    detection_fail.review_status = 'not_a_plate'
    detection_fail.not_a_plate = True
    detection_fail.reviewed_by_id = operator_id
    detection_fail.reviewed_at = timezone.now()
    detection_fail.save(
        update_fields=[
            'review_status',
            'not_a_plate',
            'reviewed_by',
            'reviewed_at',
        ]
    )
    fail_id = detection_fail.id

    def _enqueue():
        try:
            from .sync_outbox import enqueue_detection_fail
            from .models import DetectionFail

            fail = DetectionFail.objects.filter(pk=fail_id).first()
            if fail:
                enqueue_detection_fail(fail)
        except Exception:
            logger.exception('Outbox enqueue after not_a_plate failed %s', fail_id)

    transaction.on_commit(_enqueue)

    logger.info(
        'DetectionFail %s marked not_a_plate by operator %s',
        detection_fail.id,
        operator_id,
    )
    return {
        'detection_fail_id': str(detection_fail.id),
        'review_status': 'not_a_plate',
        'status': 'success',
    }


def serialize_detection_fail(fail: DetectionFail, request=None) -> Dict[str, Any]:
    def abs_url(field) -> str | None:
        if not field:
            return None
        url = field.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    return {
        'id': str(fail.id),
        'fail_type': fail.fail_type,
        'raw_ocr': fail.raw_ocr,
        'validation_error': fail.validation_error,
        'plate_confidence': (
            float(fail.plate_confidence) if fail.plate_confidence is not None else None
        ),
        'char_confidence': (
            float(fail.char_confidence) if fail.char_confidence is not None else None
        ),
        'bbox': fail.bbox,
        'camera_id': fail.camera_id,
        'direction': fail.direction,
        'full_image_url': abs_url(fail.full_image),
        'scene_b_image_url': abs_url(fail.scene_b_image),
        'crop_image_url': abs_url(fail.crop_image),
        'has_scene_b': bool(fail.has_scene_b and fail.scene_b_image),
        'scene_b_source': fail.scene_b_source or '',
        'local_data_path': fail.local_data_path,
        'review_status': fail.review_status,
        'not_a_plate': fail.not_a_plate,
        'label_ground_truth': fail.label_ground_truth or None,
        'reviewed_by': fail.reviewed_by_id,
        'reviewed_at': fail.reviewed_at.isoformat() if fail.reviewed_at else None,
        'gate_event_id': fail.gate_event_id,
        'sharpness': fail.sharpness,
        'captured_at': fail.captured_at.isoformat() if fail.captured_at else None,
        'created_at': fail.created_at.isoformat() if fail.created_at else None,
    }
