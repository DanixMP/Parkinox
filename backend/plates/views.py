"""
Views for the plates app.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 54.2
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Plate
from .serializers import PlateLookupSerializer
from utils.plate_normalizer import normalize_plate
from accounts.permissions import IsOperatorOrAdmin
import logging

logger = logging.getLogger(__name__)


def _try_detect_free_zone(raw_plate: str):
    """
    Try to detect if a plate is a Free Zone plate.
    All Free Zone plates are assigned to MAKU zone.
    
    Args:
        raw_plate: The raw plate string to test
        
    Returns:
        Tuple of (normalized_plate, 'MAKU') if detected, None otherwise
    """
    logger.info(f"Attempting MAKU Free Zone detection for plate: {raw_plate}")
    
    try:
        result = normalize_plate(raw_plate, free_zone='MAKU')
        if isinstance(result, tuple):
            logger.info(f"Successfully detected as MAKU Free Zone plate: {result[0]}")
            return result
    except ValueError as e:
        logger.debug(f"MAKU zone detection failed: {str(e)}")
    
    logger.warning(f"Free Zone detection failed for plate: {raw_plate}")
    return None


class PlateLookupView(APIView):
    """
    GET /api/plates/lookup/?q=<plate>
    
    Lookup a license plate and return associated user and wallet information.
    
    Requirements:
    - 8.1: Return user information within 500ms
    - 8.2: Return current wallet balance
    - 8.3: Return active session details if exists
    - 8.4: Return not-found indicator for unregistered plates
    - 8.5: Normalize query plate before lookup
    - 8.6: Search only active plates
    - 54.2: Respond within 500ms
    """
    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]
    
    def get(self, request):
        """
        Lookup a plate by normalized plate number.
        
        Query Parameters:
            q (str): The plate number to lookup (will be normalized)
            
        Returns:
            200: Plate information (registered or not)
            400: Invalid plate format
            500: Server error
        """
        start_time = timezone.now()
        
        # Get query parameter
        raw_plate = request.query_params.get('q', '').strip()
        
        logger.info(f"Plate lookup request: raw_plate='{raw_plate}'")
        
        if not raw_plate:
            return Response(
                {'error': 'Query parameter "q" is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Normalize the plate number (Requirement 8.5)
        try:
            normalized_result = normalize_plate(raw_plate, free_zone=None)
            
            # Check if it's a Free Zone plate (returns tuple) or national plate (returns string)
            if isinstance(normalized_result, tuple):
                normalized_plate, free_zone = normalized_result
                is_free_zone = True
            else:
                normalized_plate = normalized_result
                free_zone = None
                is_free_zone = False
        except ValueError as e:
            error_msg = str(e)
            logger.warning(f"Plate normalization failed: {error_msg}")
            # If it's an ambiguity error, try to detect as Free Zone plate
            if 'Ambiguous plate format' in error_msg:
                # Try to detect Free Zone by attempting normalization with each zone
                free_zone_detected = _try_detect_free_zone(raw_plate)
                if free_zone_detected:
                    normalized_plate, free_zone = free_zone_detected
                    is_free_zone = True
                    logger.info(f"Free Zone detection succeeded: plate={normalized_plate}, zone={free_zone}")
                else:
                    logger.error(f"Free Zone detection failed for plate: {raw_plate}")
                    return Response(
                        {
                            'error': 'فرمت پلاک مبهم است',
                            'detail': 'این پلاک می‌تواند پلاک منطقه آزاد (۵+۲ رقم) یا پلاک ملی نادرست باشد. لطفاً از فرمت API استفاده کنید (مثال: 17243FZKISH66)',
                            'is_ambiguous': True,
                            'raw_plate': raw_plate,
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                return Response(
                    {'error': f'Invalid plate format: {error_msg}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Search for active plate (Requirement 8.6)
        try:
            plate = Plate.objects.select_related(
                'user',
                'user__wallet'
            ).filter(
                plate_number=normalized_plate,
                is_active=True
            ).first()
            
            if plate:
                # Plate is registered - return user and wallet info
                user = plate.user
                wallet = user.wallet
                
                from parking.plate_utils import find_active_parked_session

                active_session = find_active_parked_session(
                    normalized_plate,
                    matched_plate=plate,
                )
                has_active_session = active_session is not None
                active_session_id = active_session.id if active_session else None
                active_session_entry_time = (
                    active_session.entry_time if active_session else None
                )
                
                response_data = {
                    'plate_number': normalized_plate,
                    'is_registered': True,
                    'is_free_zone': is_free_zone,
                    'free_zone': free_zone,
                    'user_id': user.id,
                    'user_name': user.full_name,
                    'student_id': user.student_id,
                    'user_role': user.role,
                    'wallet_balance': int(wallet.balance),
                    'has_active_session': has_active_session,
                    'active_session_id': active_session_id,
                    'active_session_entry_time': active_session_entry_time,
                }
            else:
                from parking.plate_utils import find_active_parked_session

                guest_session = find_active_parked_session(normalized_plate)
                response_data = {
                    'plate_number': normalized_plate,
                    'is_registered': False,
                    'is_free_zone': is_free_zone,
                    'free_zone': free_zone,
                    'user_id': None,
                    'user_name': None,
                    'student_id': None,
                    'user_role': None,
                    'wallet_balance': None,
                    'has_active_session': guest_session is not None,
                    'active_session_id': guest_session.id if guest_session else None,
                    'active_session_entry_time': (
                        guest_session.entry_time if guest_session else None
                    ),
                }
            
            # Validate response with serializer
            serializer = PlateLookupSerializer(data=response_data)
            serializer.is_valid(raise_exception=True)
            
            # Check response time (Requirement 54.2)
            elapsed_time = (timezone.now() - start_time).total_seconds() * 1000
            if elapsed_time > 500:
                logger.warning(
                    f"Plate lookup exceeded 500ms threshold: {elapsed_time:.2f}ms"
                )
            
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error during plate lookup: {str(e)}", exc_info=True)
            return Response(
                {'error': 'Internal server error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
