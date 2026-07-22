"""
Iranian plate validation for FastAPI detection.

Uses the same rules as Django ``backend/utils/plate_normalizer.py`` so OCR
output is accepted only when ``normalize_plate()`` would succeed on the backend.

National:  [۰-۹]{2}[letter][۰-۹]{3}-[۰-۹]{2}  e.g. ۱۲ب۳۴۵-۶۷
Free zone:   [۰-۹]{5}-[۰-۹]{2}  (zone inferred as MAKU when ambiguous, same as Django)
"""

from __future__ import annotations

import importlib.util
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple, Union


@lru_cache(maxsize=1)
def _normalizer_module():
    path = Path(__file__).resolve().parent.parent / "backend" / "utils" / "plate_normalizer.py"
    if not path.is_file():
        raise RuntimeError(f"plate_normalizer.py not found at {path}")
    spec = importlib.util.spec_from_file_location("parkinox_plate_normalizer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load plate_normalizer module spec")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def validate_detection_plate(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate OCR output against Django acceptance rules.

    Returns:
        (canonical_plate, None) on success — canonical uses Persian digits + hyphen.
        (None, error_message) when the plate must be rejected.
    """
    if not raw or not str(raw).strip():
        return None, "Plate number cannot be empty"

    text = str(raw).strip()
    normalizer = _normalizer_module()

    try:
        result: Union[str, tuple[str, str]] = normalizer.normalize_plate(text, free_zone=None)
    except ValueError as exc:
        msg = str(exc)
        if "Ambiguous plate format" in msg:
            try:
                result = normalizer.normalize_plate(text, free_zone="MAKU")
            except ValueError as inner:
                return None, str(inner)
        else:
            return None, msg

    if isinstance(result, tuple):
        canonical, _zone = result
        return canonical, None
    return result, None


def to_operator_display(canonical: str) -> str:
    """
    Spaced Persian format for operator UI / WebSocket.

    ۱۲ب۳۴۵-۶۷ → ۱۲ ب ۳۴۵ ۶۷
    ۱۷۲۴۳-۶۶ → ۱۷۲۴۳ ۶۶
    """
    national = re.match(r"^([۰-۹]{2})([ء-ی]{1,4})([۰-۹]{3})-([۰-۹]{2})$", canonical)
    if national:
        a, b, c, d = national.groups()
        return f"{a} {b} {c} {d}"

    free_zone = re.match(r"^([۰-۹]{5})-([۰-۹]{2})$", canonical)
    if free_zone:
        return f"{free_zone.group(1)} {free_zone.group(2)}"

    return canonical
