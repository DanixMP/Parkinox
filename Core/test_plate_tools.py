"""
Helpers for the FastAPI Flutter test UI: generate & validate Iranian plates,
then build the same WebSocket payload cameras emit.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from plate_validator import to_operator_display, validate_detection_plate

# Typical private-vehicle letters (exclude multi-char "الف" / "هـ" for simple randoms)
NATIONAL_LETTERS = [
    "ب", "ج", "د", "س", "ص", "ط", "ق", "ل", "م", "ن", "و", "ه", "ی",
    "پ", "ت", "ث", "ز", "ش", "ع", "ف", "ک", "گ",
]

FREE_ZONES = [
    "ANZALI",
    "ARAS",
    "ARVAND",
    "KISH",
    "MAKU",
    "CHABAHAR",
    "QESHM",
]

CAMERA_IDS = ("entry_camera", "exit_camera")


def _digits(width: int) -> str:
    return str(random.randint(0, 10**width - 1)).zfill(width)


def generate_national_raw() -> str:
    """Latin-digit spaced national plate, e.g. ``12 ب 345 67``."""
    return f"{_digits(2)} {random.choice(NATIONAL_LETTERS)} {_digits(3)} {_digits(2)}"


def generate_free_zone_raw() -> str:
    """Latin-digit free-zone number (5+2), e.g. ``1724366``."""
    return f"{_digits(5)}{_digits(2)}"


def normalize_to_standard(raw: str) -> tuple[str, str]:
    """
    Validate and return (operator_display, canonical).

    Raises ValueError when the plate is not a valid Iranian format.
    """
    canonical, err = validate_detection_plate(raw)
    if not canonical:
        raise ValueError(err or "Invalid Iranian plate format")
    return to_operator_display(canonical), canonical


def build_plate_detected_payload(
    *,
    plate_display: str,
    plate_canonical: str,
    camera_id: str,
    confidence: float = 0.95,
    char_confidence: float = 0.92,
    status: str = "unregistered",
    bbox: Optional[list[int]] = None,
) -> dict:
    if camera_id not in CAMERA_IDS:
        raise ValueError(f"camera_id must be one of {CAMERA_IDS}")
    return {
        "event_id": str(uuid.uuid4()),
        "plate_number": plate_display,
        "plate_canonical": plate_canonical,
        "camera_id": camera_id,
        "confidence": round(float(confidence), 3),
        "char_confidence": round(float(char_confidence), 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "bbox": bbox or [80, 120, 420, 220],
        "source": "test_inject",
    }


def make_random_payload(
    kind: Literal["national", "free_zone"],
    camera_id: str,
    *,
    free_zone: Optional[str] = None,
    confidence: float = 0.95,
) -> dict:
    if kind == "national":
        raw = generate_national_raw()
    elif kind == "free_zone":
        raw = generate_free_zone_raw()
    else:
        raise ValueError("kind must be 'national' or 'free_zone'")

    display, canonical = normalize_to_standard(raw)
    payload = build_plate_detected_payload(
        plate_display=display,
        plate_canonical=canonical,
        camera_id=camera_id,
        confidence=confidence,
    )
    if kind == "free_zone":
        zone = (free_zone or random.choice(FREE_ZONES)).upper()
        if zone not in FREE_ZONES:
            raise ValueError(f"Invalid free zone '{zone}'. Valid: {', '.join(FREE_ZONES)}")
        payload["free_zone"] = zone
        payload["raw_seed"] = raw
    else:
        payload["raw_seed"] = raw
    payload["kind"] = kind
    return payload
