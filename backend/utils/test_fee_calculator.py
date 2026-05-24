"""
Unit tests for parking fee calculator (proportional billing).
"""

from datetime import datetime, timedelta
from django.test import TestCase

from parking.rates import DEFAULT_RATE_SETTINGS
from .fee_calculator import calculate_fee, DEFAULT_RATES


class TestFeeCalculator(TestCase):
    """Unit tests for fee calculation logic."""

    def test_grace_period_zero_fee(self):
        entry = datetime(2024, 1, 1, 10, 0, 0)
        rates = DEFAULT_RATE_SETTINGS

        for minutes in (5, 10):
            exit = entry + timedelta(minutes=minutes)
            self.assertEqual(calculate_fee(entry, exit, False, rates=rates), 0)
            self.assertEqual(calculate_fee(entry, exit, True, rates=rates), 0)

    def test_one_hour_fee_proportional(self):
        entry = datetime(2024, 1, 1, 10, 0, 0)
        exit = entry + timedelta(hours=1)
        rates = DEFAULT_RATE_SETTINGS

        self.assertEqual(calculate_fee(entry, exit, False, rates=rates), 4166)
        self.assertEqual(calculate_fee(entry, exit, True, rates=rates), 3332)

    def test_partial_hour_proportional(self):
        entry = datetime(2024, 1, 1, 10, 0, 0)
        rates = DEFAULT_RATE_SETTINGS

        exit = entry + timedelta(minutes=11)
        self.assertEqual(calculate_fee(entry, exit, False, rates=rates), 83)

        exit = entry + timedelta(minutes=30)
        self.assertEqual(calculate_fee(entry, exit, False, rates=rates), 1666)

        exit = entry + timedelta(minutes=61)
        self.assertEqual(calculate_fee(entry, exit, False, rates=rates), 4250)

    def test_daily_cap(self):
        entry = datetime(2024, 1, 1, 10, 0, 0)
        rates = DEFAULT_RATE_SETTINGS

        exit = entry + timedelta(hours=10)
        self.assertEqual(calculate_fee(entry, exit, False, rates=rates), 40000)

        exit = entry + timedelta(hours=24)
        self.assertEqual(calculate_fee(entry, exit, False, rates=rates), 40000)

    def test_student_discount(self):
        entry = datetime(2024, 1, 1, 10, 0, 0)
        rates = DEFAULT_RATE_SETTINGS

        exit = entry + timedelta(hours=2)
        self.assertEqual(calculate_fee(entry, exit, False, rates=rates), 9166)
        self.assertEqual(calculate_fee(entry, exit, True, rates=rates), 7332)

    def test_invalid_exit_before_entry(self):
        entry = datetime(2024, 1, 1, 10, 0, 0)
        exit = datetime(2024, 1, 1, 9, 0, 0)

        with self.assertRaises(ValueError):
            calculate_fee(entry, exit, False, rates=DEFAULT_RATE_SETTINGS)

    def test_default_rates_constants(self):
        self.assertEqual(DEFAULT_RATES['rate_per_hour_toman'], 5000)
        self.assertEqual(DEFAULT_RATES['daily_cap_toman'], 40000)
        self.assertEqual(DEFAULT_RATES['grace_period_minutes'], 10)
