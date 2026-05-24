"""
Integration tests for authentication and authorization.

Requirements: 76.3, 77.5, 94.2
Tests:
- Protected endpoints require JWT
- Invalid JWT returns 401
- Role-based access control
- Health check endpoint
"""
import time

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User


def create_user(phone, password, role='student', full_name='Test User', is_active=True):
    """Helper to create a test user."""
    user = User.objects.create_user(
        phone=phone,
        password=password,
        full_name=full_name,
        role=role,
        is_active=is_active,
    )
    return user


def get_tokens(client, phone, password):
    """Helper to obtain JWT tokens via login."""
    response = client.post(
        '/api/auth/login/',
        {'phone': phone, 'password': password},
        format='json',
    )
    return response


class HealthCheckTests(TestCase):
    """
    Tests for the health check endpoint.
    Requirements: 94.1, 94.2, 94.3, 94.4, 94.5
    """

    def setUp(self):
        self.client = APIClient()

    def test_health_check_returns_200(self):
        """Health check endpoint returns 200 OK when operational."""
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_check_no_auth_required(self):
        """Health check endpoint requires no authentication."""
        # No token set — should still succeed
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_check_response_structure(self):
        """Health check response includes required fields."""
        response = self.client.get('/api/health/')
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('version', data)
        self.assertIn('database', data)
        self.assertIn('response_time_ms', data)

    def test_health_check_database_status(self):
        """Health check includes database connectivity status."""
        response = self.client.get('/api/health/')
        data = response.json()
        self.assertIn('status', data['database'])

    def test_health_check_response_time(self):
        """Health check responds within 500ms."""
        start = time.monotonic()
        response = self.client.get('/api/health/')
        elapsed_ms = (time.monotonic() - start) * 1000
        self.assertLess(elapsed_ms, 500)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class JWTAuthenticationTests(TestCase):
    """
    Tests for JWT authentication enforcement.
    Requirements: 76.1, 76.2, 76.3, 76.4, 76.5
    """

    def setUp(self):
        self.client = APIClient()
        self.operator = create_user(
            phone='09120000001',
            password='testpass123',
            role='operator',
            full_name='Test Operator',
        )

    def test_protected_endpoint_requires_jwt(self):
        """Protected endpoints return 401 without JWT token."""
        response = self.client.get('/api/plates/lookup/?q=12ب345-67')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_valid_jwt_grants_access(self):
        """Valid JWT token grants access to protected endpoints."""
        login_resp = get_tokens(self.client, '09120000001', 'testpass123')
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        token = login_resp.json()['access_token']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        # Plate lookup with a valid format plate (may return not-found, but not 401)
        response = self.client.get('/api/plates/lookup/?q=12ب345-67')
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_jwt_returns_401(self):
        """Invalid JWT token returns 401 Unauthorized."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid.token.here')
        response = self.client.get('/api/plates/lookup/?q=12ب345-67')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_bearer_token_returns_401(self):
        """Malformed Authorization header returns 401."""
        self.client.credentials(HTTP_AUTHORIZATION='NotBearer sometoken')
        response = self.client.get('/api/plates/lookup/?q=12ب345-67')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inactive_user_returns_401(self):
        """Inactive user account returns 401 even with valid token."""
        # First get a valid token
        login_resp = get_tokens(self.client, '09120000001', 'testpass123')
        token = login_resp.json()['access_token']

        # Deactivate the user
        self.operator.is_active = False
        self.operator.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/plates/lookup/?q=12ب345-67')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_endpoint_no_auth_required(self):
        """Login endpoint is accessible without authentication."""
        response = self.client.post(
            '/api/auth/login/',
            {'phone': '09120000001', 'password': 'testpass123'},
            format='json',
        )
        # Should not return 401 (may return 200 or 400 depending on credentials)
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_endpoint_no_auth_required(self):
        """Token refresh endpoint is accessible without authentication."""
        response = self.client.post(
            '/api/auth/refresh/',
            {'refresh': 'invalid_token'},
            format='json',
        )
        # Should not return 403 Forbidden (endpoint itself is AllowAny)
        self.assertNotEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class RoleBasedAccessControlTests(TestCase):
    """
    Tests for role-based access control.
    Requirements: 2.3, 2.4, 2.5, 77.1, 77.2, 77.3, 77.4, 77.5
    """

    def setUp(self):
        self.client = APIClient()
        self.student = create_user(
            phone='09120000010',
            password='testpass123',
            role='student',
            full_name='Test Student',
        )
        self.operator = create_user(
            phone='09120000011',
            password='testpass123',
            role='operator',
            full_name='Test Operator',
        )
        self.admin = create_user(
            phone='09120000012',
            password='testpass123',
            role='admin',
            full_name='Test Admin',
        )

    def _login_as(self, phone, password):
        """Login and set credentials."""
        resp = get_tokens(self.client, phone, password)
        token = resp.json()['access_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def test_student_cannot_access_plate_lookup(self):
        """Student role cannot access plate lookup (operator-only)."""
        self._login_as('09120000010', 'testpass123')
        response = self.client.get('/api/plates/lookup/?q=12ب345-67')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_can_access_plate_lookup(self):
        """Operator role can access plate lookup."""
        self._login_as('09120000011', 'testpass123')
        response = self.client.get('/api/plates/lookup/?q=12ب345-67')
        # Should not be 401 or 403
        self.assertNotIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])

    def test_admin_can_access_plate_lookup(self):
        """Admin role can access plate lookup."""
        self._login_as('09120000012', 'testpass123')
        response = self.client.get('/api/plates/lookup/?q=12ب345-67')
        self.assertNotIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])

    def test_student_cannot_access_reports(self):
        """Student role cannot access report generation endpoints."""
        self._login_as('09120000010', 'testpass123')
        response = self.client.get('/api/reports/daily/?date=2024-01-01')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_operator_can_access_reports(self):
        """Operator role can access report generation endpoints."""
        self._login_as('09120000011', 'testpass123')
        response = self.client.get('/api/reports/daily/?date=2024-01-01')
        # Should not be 401 or 403
        self.assertNotIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])

    def test_admin_can_access_reports(self):
        """Admin role can access report generation endpoints."""
        self._login_as('09120000012', 'testpass123')
        response = self.client.get('/api/reports/daily/?date=2024-01-01')
        self.assertNotIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])

    def test_unauthenticated_cannot_access_reports(self):
        """Unauthenticated requests cannot access reports."""
        response = self.client.get('/api/reports/daily/?date=2024-01-01')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_cannot_access_plate_lookup(self):
        """Unauthenticated requests cannot access plate lookup."""
        response = self.client.get('/api/plates/lookup/?q=12ب345-67')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
