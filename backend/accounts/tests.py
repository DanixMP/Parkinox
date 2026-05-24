"""
Unit tests for accounts app authentication.
Tests JWT authentication endpoints and token management.

Requirements: 1.1, 1.5, 1.6, 78.1, 78.4, 78.5, 79.1, 79.2, 79.3, 79.4, 79.5
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import User


class AuthenticationTestCase(TestCase):
    """Test cases for JWT authentication endpoints."""
    
    def setUp(self):
        """Set up test client and test users."""
        self.client = APIClient()
        
        # Create test users
        self.student = User.objects.create_user(
            phone='+989123456789',
            password='student123',
            full_name='علی رضایی',
            student_id='40012345',
            email='ali@example.com',
            role='student'
        )
        
        self.operator = User.objects.create_user(
            phone='+989123456790',
            password='operator123',
            full_name='محمد احمدی',
            email='mohammad@example.com',
            role='operator'
        )
        
        self.admin = User.objects.create_user(
            phone='+989123456791',
            password='admin123',
            full_name='سارا کریمی',
            email='sara@example.com',
            role='admin',
            is_staff=True,
            is_superuser=True
        )
    
    def test_student_login_success(self):
        """
        Test that a student can log in with valid credentials.
        Requirements: 1.1, 78.1, 79.1
        """
        url = reverse('accounts:login')
        data = {
            'phone': '+989123456789',
            'password': 'student123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['role'], 'student')
        self.assertIsNone(response.data['operator_token'])
    
    def test_operator_login_success(self):
        """
        Test that an operator can log in and receives operator_token.
        Requirements: 1.1, 1.5, 78.1, 78.4, 79.1, 79.2
        """
        url = reverse('accounts:login')
        data = {
            'phone': '+989123456790',
            'password': 'operator123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['role'], 'operator')
        self.assertIsNotNone(response.data['operator_token'])
        # Operator token should be same as access token
        self.assertEqual(response.data['operator_token'], response.data['access_token'])
    
    def test_admin_login_success(self):
        """
        Test that an admin can log in and receives operator_token.
        Requirements: 1.1, 1.5, 78.1, 78.4, 79.1, 79.2
        """
        url = reverse('accounts:login')
        data = {
            'phone': '+989123456791',
            'password': 'admin123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['role'], 'admin')
        self.assertIsNotNone(response.data['operator_token'])
    
    def test_login_invalid_credentials(self):
        """
        Test that login fails with invalid credentials.
        Requirements: 1.1, 78.5, 79.4
        """
        url = reverse('accounts:login')
        data = {
            'phone': '+989123456789',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_login_missing_phone(self):
        """
        Test that login fails when phone is missing.
        Requirements: 1.1, 78.5
        """
        url = reverse('accounts:login')
        data = {
            'password': 'student123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_missing_password(self):
        """
        Test that login fails when password is missing.
        Requirements: 1.1, 78.5
        """
        url = reverse('accounts:login')
        data = {
            'phone': '+989123456789'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_login_inactive_user(self):
        """
        Test that login fails for inactive users.
        Requirements: 1.1, 78.5
        """
        # Deactivate user
        self.student.is_active = False
        self.student.save()
        
        url = reverse('accounts:login')
        data = {
            'phone': '+989123456789',
            'password': 'student123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_token_refresh_success(self):
        """
        Test that a valid refresh token can generate a new access token.
        Requirements: 1.6, 79.3, 79.5
        """
        # First, login to get tokens
        login_url = reverse('accounts:login')
        login_data = {
            'phone': '+989123456789',
            'password': 'student123'
        }
        login_response = self.client.post(login_url, login_data, format='json')
        refresh_token = login_response.data['refresh_token']
        
        # Now test token refresh
        refresh_url = reverse('accounts:token_refresh')
        refresh_data = {
            'refresh': refresh_token
        }
        
        response = self.client.post(refresh_url, refresh_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access_token', response.data)
    
    def test_token_refresh_invalid_token(self):
        """
        Test that token refresh fails with invalid token.
        Requirements: 1.6, 79.5
        """
        url = reverse('accounts:token_refresh')
        data = {
            'refresh': 'invalid_token_string'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_token_refresh_missing_token(self):
        """
        Test that token refresh fails when token is missing.
        Requirements: 1.6, 79.5
        """
        url = reverse('accounts:token_refresh')
        data = {}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_password_hashing(self):
        """
        Test that passwords are properly hashed using PBKDF2.
        Requirements: 78.1
        """
        # Password should be hashed, not stored in plain text
        self.assertNotEqual(self.student.password, 'student123')
        self.assertTrue(self.student.password.startswith('pbkdf2_sha256$'))
        
        # User should be able to authenticate with correct password
        self.assertTrue(self.student.check_password('student123'))
        
        # User should not authenticate with wrong password
        self.assertFalse(self.student.check_password('wrongpassword'))
    
    def test_user_info_in_response(self):
        """
        Test that login response includes complete user information.
        Requirements: 1.1, 79.1
        """
        url = reverse('accounts:login')
        data = {
            'phone': '+989123456789',
            'password': 'student123'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_data = response.data['user']
        
        self.assertEqual(user_data['id'], self.student.id)
        self.assertEqual(user_data['full_name'], 'علی رضایی')
        self.assertEqual(user_data['phone'], '+989123456789')
        self.assertEqual(user_data['email'], 'ali@example.com')
        self.assertEqual(user_data['student_id'], '40012345')
        self.assertEqual(user_data['role'], 'student')
