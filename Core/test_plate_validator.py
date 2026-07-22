"""Tests for Core plate_validator (Django rule parity)."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plate_validator import to_operator_display, validate_detection_plate


class PlateValidatorTests(unittest.TestCase):
    def test_valid_national_spaced(self):
        canonical, err = validate_detection_plate("12 ب 345 67")
        self.assertIsNone(err)
        self.assertEqual(canonical, "۱۲ب۳۴۵-۶۷")

    def test_valid_compact(self):
        canonical, err = validate_detection_plate("13ب43570")
        self.assertIsNone(err)
        self.assertEqual(canonical, "۱۳ب۴۳۵-۷۰")

    def test_invalid_garbage(self):
        canonical, err = validate_detection_plate("abc123")
        self.assertIsNone(canonical)
        self.assertIn("Invalid plate format", err or "")

    def test_invalid_letter_count(self):
        canonical, err = validate_detection_plate("1ب345-67")
        self.assertIsNone(canonical)
        self.assertIsNotNone(err)

    def test_display_format(self):
        display = to_operator_display("۱۲ب۳۴۵-۶۷")
        self.assertEqual(display, "۱۲ ب ۳۴۵ ۶۷")


if __name__ == "__main__":
    unittest.main()
