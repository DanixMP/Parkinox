"""
Health check endpoint for the Parkinox backend.
Requirements: 94.1, 94.2, 94.3, 94.4, 94.5, 95.2, 95.4
"""
import time
from django.db import connection
from django.db.utils import OperationalError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status


VERSION = '1.0.0'


class HealthCheckView(APIView):
    """
    GET /api/health/

    Returns system health status including database connectivity.
    No authentication required.

    Requirements: 94.1, 94.2, 94.3, 94.4, 94.5, 95.2, 95.4
    """
    permission_classes = [AllowAny]

    def get(self, request):
        start_time = time.monotonic()

        # Check database connectivity (Requirement 94.3)
        db_status = 'ok'
        db_error = None
        try:
            connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
        except OperationalError as e:
            db_status = 'error'
            db_error = str(e)

        elapsed_ms = (time.monotonic() - start_time) * 1000

        response_data = {
            'status': 'ok' if db_status == 'ok' else 'degraded',
            'version': VERSION,
            'database': {
                'status': db_status,
            },
            'response_time_ms': round(elapsed_ms, 2),
        }

        if db_error:
            response_data['database']['error'] = db_error

        http_status = (
            status.HTTP_200_OK
            if db_status == 'ok'
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )

        return Response(response_data, status=http_status)
