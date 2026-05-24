"""
Tests for the plates app.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from accounts.models import User
from .models import Plate


class PlateLookupTestCase(TestCase):
    """Test plate lookup functionality."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create an operator user for authentication
        self.operator = User.objects.create_user(
            phone='+989123456789',
            password='testpass123',
            full_name='Test Operator',
            role='operator'
        )
        
        # Create a student user with a registered plate
        self.student = User.objects.create_user(
            phone='+989123456788',
            password='testpass123',
            full_name='Test Student',
            role='student',
            student_id='12345678'
        )
        
        # Create a registered national plate
        self.national_plate = Plate.objects.create(
            user=self.student,
            plate_number='۱۲ب۳۴۵-۶۷',
            is_active=True
        )
        
        # Create a registered Free Zone plate
        self.fz_plate = Plate.objects.create(
            user=self.student,
            plate_number='۱۷۲۴۳-۶۶',
            is_free_zone=True,
            free_zone='KISH',
            is_active=True
        )
        
        # Authenticate as operator
        self.client.force_authenticate(user=self.operator)

    def test_lookup_national_plate_api_format(self):
        """Test looking up a national plate using API format."""
        url = reverse('plates:plate-lookup')
        response = self.client.get(url, {'q': '12B345IR67'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['is_registered'])
        self.assertFalse(data['is_free_zone'])
        self.assertEqual(data['plate_number'], '۱۲ب۳۴۵-۶۷')
        self.assertEqual(data['user_name'], 'Test Student')

    def test_lookup_free_zone_plate_api_format(self):
        """Test looking up a Free Zone plate using API format."""
        url = reverse('plates:plate-lookup')
        response = self.client.get(url, {'q': '17243FZKISH66'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data['is_registered'])
        self.assertTrue(data['is_free_zone'])
        self.assertEqual(data['free_zone'], 'KISH')
        self.assertEqual(data['plate_number'], '۱۷۲۴۳-۶۶')
        self.assertEqual(data['user_name'], 'Test Student')

    def test_lookup_ambiguous_plate_format(self):
        """Test that ambiguous plate format (7 digits) is handled gracefully."""
        url = reverse('plates:plate-lookup')
        response = self.client.get(url, {'q': '1724366'})
        
        # Should either succeed (if Free Zone detection works) or return ambiguous error
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            self.assertTrue(data['is_free_zone'])
            self.assertEqual(data['plate_number'], '۱۷۲۴۳-۶۶')
        else:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            data = response.json()
            self.assertIn('مبهم', data['error'])

    def test_lookup_unregistered_plate(self):
        """Test looking up an unregistered plate."""
        url = reverse('plates:plate-lookup')
        response = self.client.get(url, {'q': '99A999IR99'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertFalse(data['is_registered'])
        self.assertIsNone(data['user_name'])
        self.assertEqual(data['plate_number'], '۹۹الف۹۹۹-۹۹')

    def test_lookup_invalid_plate_format(self):
        """Test looking up with invalid plate format."""
        url = reverse('plates:plate-lookup')
        response = self.client.get(url, {'q': 'invalid'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn('error', data)

    def test_lookup_requires_authentication(self):
        """Test that plate lookup requires authentication."""
        self.client.force_authenticate(user=None)
        url = reverse('plates:plate-lookup')
        response = self.client.get(url, {'q': '12B345IR67'})
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lookup_requires_operator_role(self):
        """Test that plate lookup requires operator or admin role."""
        # Create a student user and authenticate as them
        student = User.objects.create_user(
            phone='+989123456787',
            password='testpass123',
            full_name='Another Student',
            role='student'
        )
        self.client.force_authenticate(user=student)
        
        url = reverse('plates:plate-lookup')
        response = self.client.get(url, {'q': '12B345IR67'})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)