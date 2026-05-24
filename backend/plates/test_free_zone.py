"""
Tests for Free Zone plate support.

This module tests the Free Zone plate functionality including:
- Normalization of Free Zone plates (5+2 digit format)
- Registration of Free Zone plates
- Lookup of Free Zone plates
- API format conversion

Note: Free Zone plates have the same NUMBER format as national plates (5+2 digits),
but without a letter. The zone is specified separately.
"""

from django.test import TestCase
from accounts.models import User
from plates.models import Plate
from utils.plate_normalizer import normalize_plate, to_api_format, VALID_FREE_ZONES


class FreeZonePlateNormalizerTest(TestCase):
    """Test Free Zone plate normalization."""
    
    def test_normalize_free_zone_plate_with_zone_param(self):
        """Test normalizing Free Zone plate with zone parameter."""
        result = normalize_plate("17243-66", free_zone="ANZALI")
        self.assertIsInstance(result, tuple)
        plate, zone = result
        self.assertEqual(plate, "۱۷۲۴۳-۶۶")
        self.assertEqual(zone, "ANZALI")
    
    def test_normalize_free_zone_plate_without_hyphen(self):
        """Test normalizing Free Zone plate without hyphen."""
        result = normalize_plate("1724366", free_zone="KISH")
        self.assertIsInstance(result, tuple)
        plate, zone = result
        self.assertEqual(plate, "۱۷۲۴۳-۶۶")
        self.assertEqual(zone, "KISH")
    
    def test_normalize_free_zone_plate_with_spaces(self):
        """Test normalizing Free Zone plate with spaces."""
        result = normalize_plate("17 243 66", free_zone="KISH")
        self.assertIsInstance(result, tuple)
        plate, zone = result
        self.assertEqual(plate, "۱۷۲۴۳-۶۶")
        self.assertEqual(zone, "KISH")
    
    def test_normalize_free_zone_api_format(self):
        """Test normalizing Free Zone plate in API format."""
        result = normalize_plate("17243FZKISH66")
        self.assertIsInstance(result, tuple)
        plate, zone = result
        self.assertEqual(plate, "۱۷۲۴۳-۶۶")
        self.assertEqual(zone, "KISH")
    
    def test_normalize_all_free_zones(self):
        """Test normalizing all valid Free Zones."""
        for zone in VALID_FREE_ZONES:
            result = normalize_plate(f"17243-66", free_zone=zone)
            self.assertIsInstance(result, tuple)
            plate, returned_zone = result
            self.assertEqual(plate, f"۱۷۲۴۳-۶۶")
            self.assertEqual(returned_zone, zone)
    
    def test_normalize_invalid_free_zone(self):
        """Test normalizing invalid Free Zone raises error."""
        with self.assertRaises(ValueError) as context:
            normalize_plate("17243-66", free_zone="INVALID")
        self.assertIn("Invalid Free Zone", str(context.exception))
    
    def test_normalize_ambiguous_plate_without_zone(self):
        """Test that 5+2 digit plate without zone raises ambiguous error."""
        with self.assertRaises(ValueError) as context:
            normalize_plate("17243-66")
        self.assertIn("Ambiguous plate format", str(context.exception))
    
    def test_normalize_national_plate_still_works(self):
        """Test that national plate normalization still works."""
        result = normalize_plate("12ب345-67")
        self.assertIsInstance(result, str)
        self.assertEqual(result, "۱۲ب۳۴۵-۶۷")
    
    def test_to_api_format_free_zone(self):
        """Test converting Free Zone plate to API format."""
        api_format = to_api_format("۱۷۲۴۳-۶۶", free_zone="KISH")
        self.assertEqual(api_format, "17243FZKISH66")
    
    def test_to_api_format_national_plate(self):
        """Test converting national plate to API format still works."""
        api_format = to_api_format("۱۲ب۳۴۵-۶۷")
        self.assertEqual(api_format, "12B345IR67")
    
    def test_to_api_format_free_zone_without_zone_param_raises_error(self):
        """Test that converting Free Zone plate without zone param raises error."""
        with self.assertRaises(ValueError) as context:
            to_api_format("۱۷۲۴۳-۶۶")
        self.assertIn("Free Zone name required", str(context.exception))


class FreeZonePlateModelTest(TestCase):
    """Test Free Zone plate model functionality."""
    
    def setUp(self):
        """Set up test user."""
        self.user = User.objects.create_user(
            phone='09123456789',
            password='testpass123',
            full_name='Test User',
            role='student'
        )
    
    def test_create_free_zone_plate(self):
        """Test creating a Free Zone plate."""
        plate = Plate(
            user=self.user,
            plate_number='17243-66',
            is_primary=True,
            is_verified=False
        )
        # Set free_zone before saving
        plate.free_zone = 'KISH'
        plate.save()
        
        # Reload from database
        plate.refresh_from_db()
        
        self.assertEqual(plate.plate_number, '۱۷۲۴۳-۶۶')
        self.assertTrue(plate.is_free_zone)
        self.assertEqual(plate.free_zone, 'KISH')
    
    def test_create_national_plate(self):
        """Test creating a national plate still works."""
        plate = Plate(
            user=self.user,
            plate_number='12ب345-67',
            is_primary=True,
            is_verified=False
        )
        plate.save()
        
        # Reload from database
        plate.refresh_from_db()
        
        self.assertEqual(plate.plate_number, '۱۲ب۳۴۵-۶۷')
        self.assertFalse(plate.is_free_zone)
        self.assertIsNone(plate.free_zone)
    
    def test_create_multiple_free_zone_plates(self):
        """Test creating multiple Free Zone plates for different zones."""
        zones = ['KISH', 'QESHM', 'ANZALI']
        
        for i, zone in enumerate(zones):
            user = User.objects.create_user(
                phone=f'0912345678{i}',
                password='testpass123',
                full_name=f'Test User {i}',
                role='student'
            )
            
            plate = Plate(
                user=user,
                plate_number=f'1724{i}-66',
                is_primary=True,
                is_verified=False
            )
            plate.free_zone = zone
            plate.save()
            
            plate.refresh_from_db()
            self.assertTrue(plate.is_free_zone)
            self.assertEqual(plate.free_zone, zone)
    
    def test_free_zone_plate_string_representation(self):
        """Test string representation of Free Zone plate."""
        plate = Plate(
            user=self.user,
            plate_number='17243-66',
            is_primary=True,
            is_verified=False
        )
        plate.free_zone = 'KISH'
        plate.save()
        
        expected = f"۱۷۲۴۳-۶۶ (اصلی) - {self.user.full_name}"
        self.assertEqual(str(plate), expected)
    
    def test_free_zone_plate_validation(self):
        """Test that invalid Free Zone raises validation error."""
        from django.core.exceptions import ValidationError
        
        plate = Plate(
            user=self.user,
            plate_number='17243-66',
            is_primary=True,
            is_verified=False
        )
        plate.free_zone = 'INVALID'
        
        with self.assertRaises(ValidationError):
            plate.full_clean()


class FreeZonePlateQueryTest(TestCase):
    """Test querying Free Zone plates."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = User.objects.create_user(
            phone='09123456781',
            password='testpass123',
            full_name='User 1',
            role='student'
        )
        
        self.user2 = User.objects.create_user(
            phone='09123456782',
            password='testpass123',
            full_name='User 2',
            role='student'
        )
        
        # Create Free Zone plate
        self.fz_plate = Plate(
            user=self.user1,
            plate_number='17243-66',
            is_primary=True,
            is_verified=True
        )
        self.fz_plate.free_zone = 'KISH'
        self.fz_plate.save()
        
        # Create national plate
        self.nat_plate = Plate.objects.create(
            user=self.user2,
            plate_number='12ب345-67',
            is_primary=True,
            is_verified=True
        )
    
    def test_filter_free_zone_plates(self):
        """Test filtering only Free Zone plates."""
        fz_plates = Plate.objects.filter(is_free_zone=True)
        self.assertEqual(fz_plates.count(), 1)
        self.assertEqual(fz_plates.first().free_zone, 'KISH')
    
    def test_filter_national_plates(self):
        """Test filtering only national plates."""
        nat_plates = Plate.objects.filter(is_free_zone=False)
        self.assertEqual(nat_plates.count(), 1)
        self.assertIsNone(nat_plates.first().free_zone)
    
    def test_filter_by_specific_zone(self):
        """Test filtering by specific Free Zone."""
        kish_plates = Plate.objects.filter(free_zone='KISH')
        self.assertEqual(kish_plates.count(), 1)
        self.assertEqual(kish_plates.first().plate_number, '۱۷۲۴۳-۶۶')
    
    def test_lookup_free_zone_plate_by_number(self):
        """Test looking up Free Zone plate by plate number."""
        plate = Plate.objects.filter(
            plate_number='۱۷۲۴۳-۶۶',
            is_active=True
        ).first()
        
        self.assertIsNotNone(plate)
        self.assertTrue(plate.is_free_zone)
        self.assertEqual(plate.free_zone, 'KISH')
        self.assertEqual(plate.user, self.user1)
