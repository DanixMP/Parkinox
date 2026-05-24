"""
Views for parking app.
Handles gate events and parking sessions.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import ParkingSession
from .services import ParkingSessionService
from .gate_event_service import confirm_gate_event
from .plate_utils import (
    find_active_parked_session,
    link_session_to_plate,
    normalize_plate_strict,
    resolve_session_registration,
)
from .rates import get_active_rate_settings
from plates.models import Plate
from accounts.permissions import IsOperator
from utils.plate_normalizer import normalize_plate
from utils.fee_calculator import calculate_fee


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOperator])
def create_gate_event(request):
    """
    Create gate event from operator app (entry or exit).

    POST /api/parking/gate-events/
    """
    if request.user.role not in ['operator', 'admin']:
        return Response(
            {'error': 'Operator access required'},
            status=status.HTTP_403_FORBIDDEN,
        )

    camera_id = request.data.get('camera_id')
    direction = request.data.get('direction')
    plate_raw = request.data.get('plate_raw', '')
    plate_confirmed = request.data.get('plate_confirmed', '')

    if not camera_id:
        return Response(
            {'error': 'camera_id is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if direction not in ['entry', 'exit']:
        return Response(
            {'error': 'Direction must be "entry" or "exit"'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not plate_confirmed:
        return Response(
            {'error': 'plate_confirmed is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    confidence_score = request.data.get('confidence_score')
    was_edited = bool(request.data.get('was_edited', False))
    was_auto_approved = bool(request.data.get('was_auto_approved', False))

    try:
        result = confirm_gate_event(
            operator_id=request.user.id,
            camera_id=camera_id,
            direction=direction,
            plate_raw=plate_raw,
            plate_confirmed=plate_confirmed,
            confidence_score=confidence_score,
            was_edited=was_edited,
            was_auto_approved=was_auto_approved,
        )
    except ValidationError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(
            {'error': f'Failed to process gate event: {e}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response(
        {
            'gate_event_id': result['gate_event_id'],
            'session_id': result['session_id'],
            'status': result['status'],
            'payment_status': result['payment_status'],
            'fee': result['fee'],
            'fee_charged': result['fee'],
            'matched_user': result['matched_user'],
            'wallet_balance': result['wallet_balance'],
            'wallet_sufficient': result['wallet_sufficient'],
        },
        status=status.HTTP_201_CREATED,
    )


def _serialize_parked_session(session: ParkingSession) -> dict:
    """Build API payload for a parked session with live registration resolution."""
    is_registered, plate_rec, plate_number = resolve_session_registration(session)

    if is_registered and plate_rec and session.plate_id is None:
        link_session_to_plate(session, plate_rec)

    user_name = 'Guest'
    user_phone = None
    wallet_balance = None
    user_role = None
    is_student = False
    is_free_zone = False
    free_zone = None

    if is_registered and plate_rec:
        user = plate_rec.user
        user_name = user.full_name
        user_phone = user.phone
        user_role = user.role
        is_student = user.role == 'student'
        is_free_zone = plate_rec.is_free_zone
        free_zone = plate_rec.free_zone
        try:
            wallet_balance = int(user.wallet.balance)
        except Exception:
            wallet_balance = None

    duration_minutes = int(
        (timezone.now() - session.entry_time).total_seconds() // 60
    )
    estimated_fee = calculate_fee(
        entry_time=session.entry_time,
        exit_time=timezone.now(),
        is_student=is_student,
    )

    return {
        'id': session.id,
        'plate_number': plate_number,
        'user_name': user_name,
        'user_phone': user_phone,
        'user_role': user_role,
        'wallet_balance': wallet_balance,
        'entry_time': session.entry_time.isoformat(),
        'duration_minutes': duration_minutes,
        'estimated_fee': estimated_fee,
        'is_registered': is_registered,
        'is_student': is_student,
        'is_free_zone': is_free_zone,
        'free_zone': free_zone,
    }


def _serialize_unpaid_session(session: ParkingSession) -> dict:
    is_registered, plate_rec, plate_number = resolve_session_registration(session)
    user_name = plate_rec.user.full_name if is_registered and plate_rec else 'Guest'
    is_free_zone = plate_rec.is_free_zone if is_registered and plate_rec else False
    free_zone = plate_rec.free_zone if is_registered and plate_rec else None
    return {
        'id': session.id,
        'plate_number': plate_number,
        'user_name': user_name,
        'entry_time': session.entry_time.isoformat(),
        'exit_time': session.exit_time.isoformat() if session.exit_time else None,
        'duration_minutes': session.duration_minutes,
        'fee_charged': float(session.fee_charged),
        'status': session.status,
        'payment_method': session.payment_method,
        'is_registered': is_registered,
        'is_free_zone': is_free_zone,
        'free_zone': free_zone,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOperator])
def get_parked_vehicles(request):
    """
    List parking sessions.

    GET /api/parking/sessions/?status=parked   — currently inside
    GET /api/parking/sessions/?status=unpaid   — exited, awaiting payment
    """
    status_filter = request.query_params.get('status', 'parked')

    if status_filter == 'unpaid':
        sessions = (
            ParkingSession.objects.filter(status='unpaid')
            .select_related('plate', 'plate__user')
            .order_by('-exit_time')
        )
        results = [_serialize_unpaid_session(s) for s in sessions]
        return Response({'count': len(results), 'results': results})

    sessions = (
        ParkingSession.objects.filter(status='parked')
        .select_related('plate', 'plate__user', 'plate__user__wallet')
        .order_by('-entry_time')
    )
    results = [_serialize_parked_session(s) for s in sessions]

    return Response({
        'count': len(results),
        'results': results,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOperator])
def get_session(request, session_id):
    """
    Get session details by ID.

    GET /api/parking/sessions/{id}/
    """
    session = get_object_or_404(
        ParkingSession.objects.select_related('plate', 'plate__user', 'plate__user__wallet'),
        id=session_id,
    )

    is_registered, plate_rec, plate_number = resolve_session_registration(session)
    user_name = plate_rec.user.full_name if is_registered and plate_rec else 'Guest'
    wallet_balance = None
    if is_registered and plate_rec:
        try:
            wallet_balance = int(plate_rec.user.wallet.balance)
        except Exception:
            pass

    return Response({
        'id': session.id,
        'plate_number': plate_number,
        'user_name': user_name,
        'wallet_balance': wallet_balance,
        'entry_time': session.entry_time.isoformat(),
        'exit_time': session.exit_time.isoformat() if session.exit_time else None,
        'duration_minutes': session.duration_minutes,
        'fee_charged': float(session.fee_charged),
        'status': session.status,
        'payment_method': session.payment_method,
        'is_registered': is_registered,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOperator])
def record_cash_payment(request, session_id):
    """
    Record cash payment for unpaid session.

    POST /api/parking/sessions/{id}/cash-payment/
    """
    notes = request.data.get('notes')

    try:
        session = ParkingSessionService.record_cash_payment(
            session_id=session_id,
            operator_id=request.user.id,
            notes=notes,
        )

        return Response({
            'session_id': session.id,
            'status': session.status,
            'payment_method': session.payment_method,
            'message': 'Cash payment recorded successfully',
        })
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOperator])
def waive_fee(request, session_id):
    """
    Waive parking fee for session.

    POST /api/parking/sessions/{id}/waive-fee/
    """
    try:
        session = ParkingSessionService.waive_fee(
            session_id=session_id,
            operator_id=request.user.id,
        )

        return Response({
            'session_id': session.id,
            'status': session.status,
            'fee_charged': float(session.fee_charged),
            'message': 'Fee waived successfully',
        })
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated, IsOperator])
def rate_config(request):
    """
    GET /api/parking/rates/ — active rate configuration.
    PATCH /api/parking/rates/ — update active profile (operator/admin).

    Body (PATCH, all optional): rate_per_hour, daily_cap,
    grace_period_minutes, student_discount_percent
    """
    if request.method == 'GET':
        settings = get_active_rate_settings()
        return Response({
            'rate_per_hour': settings.rate_per_hour_toman,
            'daily_cap': settings.daily_cap_toman,
            'grace_period_minutes': settings.grace_period_minutes,
            'student_discount_percent': settings.student_discount_percent,
        })

    if request.user.role not in ['operator', 'admin']:
        return Response(
            {'error': 'Operator access required'},
            status=status.HTTP_403_FORBIDDEN,
        )

    allowed_fields = {
        'rate_per_hour',
        'daily_cap',
        'grace_period_minutes',
        'student_discount_percent',
    }
    if not any(k in request.data for k in allowed_fields):
        return Response(
            {'error': 'Provide at least one of: rate_per_hour, daily_cap, '
                     'grace_period_minutes, student_discount_percent'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from decimal import Decimal
    from .models import RateConfig

    config = RateConfig.objects.filter(is_active=True).order_by('-updated_at').first()
    if config is None:
        config = RateConfig.objects.order_by('-updated_at').first()
    if config is None:
        config = RateConfig.objects.create(
            name='Standard',
            rate_per_hour=Decimal('5000'),
            daily_cap=Decimal('40000'),
            grace_period_minutes=10,
            student_discount_percent=80,
            is_active=True,
        )

    def _int_field(key, current, min_v, max_v):
        if key not in request.data:
            return None, None
        raw = request.data.get(key)
        if raw is None:
            return None, None
        try:
            val = int(raw)
        except (TypeError, ValueError):
            return None, Response(
                {'error': f'{key} must be an integer'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if val < min_v or val > max_v:
            return None, Response(
                {'error': f'{key} must be between {min_v} and {max_v}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return val, None

    err = None
    if 'rate_per_hour' in request.data:
        val, err = _int_field('rate_per_hour', None, 0, 50_000_000)
        if err:
            return err
        if val is not None:
            config.rate_per_hour = Decimal(val)

    if 'daily_cap' in request.data:
        val, err = _int_field('daily_cap', None, 0, 500_000_000)
        if err:
            return err
        if val is not None:
            config.daily_cap = Decimal(val)

    if 'grace_period_minutes' in request.data:
        val, err = _int_field('grace_period_minutes', None, 0, 24 * 60)
        if err:
            return err
        if val is not None:
            config.grace_period_minutes = val

    if 'student_discount_percent' in request.data:
        val, err = _int_field('student_discount_percent', None, 0, 100)
        if err:
            return err
        if val is not None:
            config.student_discount_percent = val

    if int(config.rate_per_hour) > int(config.daily_cap):
        return Response(
            {'error': 'daily_cap must be greater than or equal to rate_per_hour'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    config.is_active = True
    config.save()

    settings = get_active_rate_settings()
    return Response({
        'rate_per_hour': settings.rate_per_hour_toman,
        'daily_cap': settings.daily_cap_toman,
        'grace_period_minutes': settings.grace_period_minutes,
        'student_discount_percent': settings.student_discount_percent,
        'message': 'Rate configuration updated',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOperator])
def lookup_plate(request):
    """
    Look up a license plate to check if it's registered.

    GET /api/parking/plates/lookup/?plate=12B345IR17
    GET /api/parking/plates/lookup/?plate=17243FZKISH66
    """
    plate_raw = request.query_params.get('plate')

    if not plate_raw:
        return Response(
            {'found': False, 'error': 'Plate parameter is required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        normalized_result = normalize_plate(plate_raw, free_zone=None)
        
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
        # If it's an ambiguity error, provide helpful guidance
        if 'Ambiguous plate format' in error_msg:
            return Response(
                {
                    'found': False,
                    'error': 'فرمت پلاک مبهم است',
                    'detail': 'این پلاک می‌تواند پلاک منطقه آزاد (۵+۲ رقم) یا پلاک ملی نادرست باشد. لطفاً از فرمت API استفاده کنید (مثال: 17243FZKISH66)',
                    'is_ambiguous': True,
                    'raw_plate': plate_raw,
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            {'found': False, 'error': error_msg},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        plate = Plate.objects.select_related('user', 'user__wallet').get(
            plate_number=normalized_plate,
            is_active=True,
        )

        active_session = find_active_parked_session(
            normalized_plate,
            matched_plate=plate,
        )

        wallet_balance = None
        try:
            wallet_balance = int(plate.user.wallet.balance)
        except Exception:
            pass

        wallet_id = None
        try:
            wallet_id = plate.user.wallet.id
        except Exception:
            pass

        return Response({
            'found': True,
            'is_registered': True,
            'is_free_zone': is_free_zone,
            'free_zone': free_zone,
            'plate_number': plate.plate_number,
            'user': {
                'id': plate.user.id,
                'full_name': plate.user.full_name,
                'phone': plate.user.phone,
            },
            'wallet_id': wallet_id,
            'wallet_balance': wallet_balance,
            'has_active_session': active_session is not None,
            'active_session_id': active_session.id if active_session else None,
            'active_session_entry_time': (
                active_session.entry_time.isoformat() if active_session else None
            ),
            'is_active': plate.is_active,
            'is_primary': plate.is_primary,
        })

    except Plate.DoesNotExist:
        guest_session = find_active_parked_session(normalized_plate)

        return Response({
            'found': True,
            'is_registered': False,
            'is_free_zone': is_free_zone,
            'free_zone': free_zone,
            'plate_number': normalized_plate,
            'user': None,
            'wallet_balance': None,
            'has_active_session': guest_session is not None,
            'active_session_id': guest_session.id if guest_session else None,
            'active_session_entry_time': (
                guest_session.entry_time.isoformat() if guest_session else None
            ),
            'is_active': None,
            'is_primary': None,
        })
