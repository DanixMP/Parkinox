"""
Plate normalization and parking session lookup helpers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from plates.models import Plate
from utils.plate_normalizer import normalize_plate

from .models import ParkingSession


def normalize_plate_strict(raw: Optional[str]) -> Optional[str]:
    """
    Normalize plate for storage/lookup; raises ValueError if invalid.
    All Free Zone plates are automatically assigned to MAKU zone.
    """
    if not raw or not str(raw).strip():
        return None
    
    raw_str = str(raw).strip()
    
    try:
        result = normalize_plate(raw_str, free_zone=None)
        # If it's a tuple (Free Zone plate), return just the normalized plate
        if isinstance(result, tuple):
            return result[0]
        return result
    except ValueError as e:
        error_msg = str(e)
        # If it's an ambiguity error, assume it's a MAKU Free Zone plate
        if 'Ambiguous plate format' in error_msg:
            try:
                result = normalize_plate(raw_str, free_zone='MAKU')
                if isinstance(result, tuple):
                    # Successfully detected as MAKU Free Zone plate
                    return result[0]
            except ValueError:
                pass
            
            # If MAKU detection failed, raise the original error
            raise ValueError(f"Ambiguous plate format: '{raw_str}'. Could not detect as MAKU Free Zone plate.")
        else:
            # Re-raise other errors
            raise


def find_plate_record(normalized_plate: str) -> Optional[Plate]:
    if not normalized_plate:
        return None
    return (
        Plate.objects.filter(plate_number=normalized_plate, is_active=True)
        .select_related('user', 'user__wallet')
        .first()
    )


def _guest_session_matches(session: ParkingSession, normalized_plate: str) -> bool:
    if not session.guest_plate_number:
        return False
    if session.guest_plate_number == normalized_plate:
        return True
    try:
        return normalize_plate(session.guest_plate_number) == normalized_plate
    except ValueError:
        return False


def find_active_parked_session(
    normalized_plate: str,
    *,
    matched_plate: Optional[Plate] = None,
) -> Optional[ParkingSession]:
    """
    Find the active parked session for a plate number.

    Matches registered sessions by plate FK and guest sessions by
    guest_plate_number (including legacy non-normalized values).
    """
    if not normalized_plate:
        return None

    plate = matched_plate or find_plate_record(normalized_plate)

    if plate:
        session = (
            ParkingSession.objects.filter(plate=plate, status='parked')
            .select_related('plate', 'plate__user', 'plate__user__wallet')
            .first()
        )
        if session:
            return session

    for session in (
        ParkingSession.objects.filter(status='parked', guest_plate_number__isnull=False)
        .select_related('plate', 'plate__user', 'plate__user__wallet')
    ):
        if _guest_session_matches(session, normalized_plate):
            if plate and session.plate_id is None:
                session.plate = plate
                session.guest_plate_number = None
                session.save(update_fields=['plate', 'guest_plate_number'])
            return session

    return None


def link_session_to_plate(session: ParkingSession, plate: Plate) -> ParkingSession:
    """Attach a registered plate to a session that was stored as guest."""
    if session.plate_id is None:
        session.plate = plate
        session.guest_plate_number = None
        session.save(update_fields=['plate', 'guest_plate_number'])
    return session


def resolve_session_registration(
    session: ParkingSession,
) -> Tuple[bool, Optional[Plate], str]:
    """
    Resolve whether a parked session belongs to a registered user.

    Returns (is_registered, plate_record, display_plate_number).
    """
    if session.plate_id:
        return True, session.plate, session.plate.plate_number

    plate_number = session.guest_plate_number or ''
    normalized = None
    try:
        normalized = normalize_plate_strict(plate_number)
    except ValueError:
        normalized = plate_number

    plate = find_plate_record(normalized) if normalized else None
    if plate:
        return True, plate, plate.plate_number

    return False, None, plate_number
