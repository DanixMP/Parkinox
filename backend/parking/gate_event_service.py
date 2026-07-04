"""
Gate event confirmation and rejection processing.

Shared by the REST API and WebSocket consumer so entry/exit handling stays consistent.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from django.db import transaction

from .models import GateEvent
from .cross_camera_guard import cross_camera_conflict
from .plate_utils import find_plate_record, normalize_plate_strict
from .services import ParkingSessionService

logger = logging.getLogger(__name__)


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
) -> Dict[str, Any]:
    """
    Create a confirmed gate event and open or close the related parking session.

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
            plate_raw_normalized = plate_confirmed_normalized

    if not plate_confirmed_normalized:
        raise ValueError('plate_confirmed is required')

    conflict = cross_camera_conflict(plate_confirmed_normalized, direction)
    if conflict:
        raise ValueError(conflict)

    matched_plate = find_plate_record(plate_confirmed_normalized)
    matched_user = matched_plate.user if matched_plate else None

    gate_event = GateEvent.objects.create(
        camera_id=camera_id,
        direction=direction,
        plate_raw=plate_raw_normalized,
        plate_confirmed=plate_confirmed_normalized,
        confidence_score=(
            Decimal(str(confidence_score)) if confidence_score is not None else None
        ),
        was_edited=was_edited,
        was_auto_approved=was_auto_approved,
        was_rejected=False,
        operator_id=operator_id,
        matched_user=matched_user,
        matched_plate=matched_plate,
    )

    session_id = None
    fee = 0
    payment_status = 'none'
    wallet_balance = None
    wallet_sufficient = None

    if direction == 'entry':
        session = ParkingSessionService.create_entry_session(gate_event)
        session_id = session.id
        payment_status = 'parked'
    else:
        result = ParkingSessionService.close_exit_session(gate_event)
        if result['session']:
            session_id = result['session'].id
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

    return {
        'event_id': gate_event.id,
        'gate_event_id': gate_event.id,
        'session_id': session_id,
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
