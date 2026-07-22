"""Unit tests for Flutter test inject helpers."""
from test_plate_tools import (
    generate_free_zone_raw,
    generate_national_raw,
    make_random_payload,
    normalize_to_standard,
)


def test_national_random_is_standard():
    raw = generate_national_raw()
    display, canonical = normalize_to_standard(raw)
    assert " " in display
    assert "-" in canonical
    assert len(canonical) >= 8


def test_free_zone_random_is_standard():
    raw = generate_free_zone_raw()
    display, canonical = normalize_to_standard(raw)
    assert " " in display
    assert "-" in canonical
    # free zone: 5 digits + hyphen + 2 digits (Persian)
    assert canonical.count("-") == 1


def test_make_random_payload_national():
    payload = make_random_payload("national", "entry_camera")
    assert payload["camera_id"] == "entry_camera"
    assert payload["plate_number"]
    assert payload["plate_canonical"]
    assert payload["kind"] == "national"


def test_make_random_payload_free_zone():
    payload = make_random_payload("free_zone", "exit_camera", free_zone="KISH")
    assert payload["camera_id"] == "exit_camera"
    assert payload["free_zone"] == "KISH"
    assert payload["kind"] == "free_zone"


def test_invalid_plate_rejected():
    try:
        normalize_to_standard("NOT-A-PLATE")
        assert False, "expected ValueError"
    except ValueError:
        pass
