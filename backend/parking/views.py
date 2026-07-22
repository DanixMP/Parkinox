"""
Views for parking app.
Handles gate events and parking sessions.
"""

import json
import logging
from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime

from .models import DetectionFail, ParkingSession
from .services import ParkingSessionService
from .gate_event_service import confirm_gate_event
from .detection_fail_service import (
    review_correct,
    review_not_a_plate,
    serialize_detection_fail,
)
from .season_service import get_season_started_at, reset_operational_season
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

logger = logging.getLogger(__name__)


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
    client_event_uuid = request.data.get('client_event_uuid') or request.data.get('event_uuid')
    detection_event_id = request.data.get('detection_event_id')

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
            client_event_uuid=client_event_uuid,
            detection_event_id=detection_event_id,
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
            'event_uuid': result.get('event_uuid'),
            'session_id': result['session_id'],
            'session_uuid': result.get('session_uuid'),
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


def _active_session_lookup_fields(session: ParkingSession | None, *, is_student: bool = False) -> dict:
    """Shared session fields for plate lookup (exit approval UI)."""
    if session is None:
        return {
            'has_active_session': False,
            'active_session_id': None,
            'active_session_entry_time': None,
            'duration_minutes': None,
            'estimated_fee': None,
            'entry_camera_id': None,
        }

    # Prefer already-loaded entry_event; otherwise fetch with select_related.
    entry_event = getattr(session, 'entry_event', None)
    if entry_event is None and session.entry_event_id:
        from .models import GateEvent

        entry_event = (
            GateEvent.objects.filter(pk=session.entry_event_id)
            .only('id', 'camera_id')
            .first()
        )

    duration_minutes = int(
        (timezone.now() - session.entry_time).total_seconds() // 60
    )
    estimated_fee = calculate_fee(
        entry_time=session.entry_time,
        exit_time=timezone.now(),
        is_student=is_student,
    )
    return {
        'has_active_session': True,
        'active_session_id': session.id,
        'active_session_entry_time': session.entry_time.isoformat(),
        'duration_minutes': duration_minutes,
        'estimated_fee': estimated_fee,
        'entry_camera_id': entry_event.camera_id if entry_event else None,
    }


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
    season_started_at = get_season_started_at()

    if status_filter == 'unpaid':
        sessions = (
            ParkingSession.objects.filter(
                status='unpaid',
                entry_time__gte=season_started_at,
            )
            .select_related('plate', 'plate__user')
            .order_by('-exit_time')
        )
        results = [_serialize_unpaid_session(s) for s in sessions]
        return Response({'count': len(results), 'results': results})

    sessions = (
        ParkingSession.objects.filter(
            status='parked',
            entry_time__gte=season_started_at,
        )
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

        is_student = getattr(plate.user, 'role', None) == 'student'
        session_fields = _active_session_lookup_fields(
            active_session, is_student=is_student
        )

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
            **session_fields,
            'is_active': plate.is_active,
            'is_primary': plate.is_primary,
        })

    except Plate.DoesNotExist:
        guest_session = find_active_parked_session(normalized_plate)
        session_fields = _active_session_lookup_fields(
            guest_session, is_student=False
        )

        return Response({
            'found': True,
            'is_registered': False,
            'is_free_zone': is_free_zone,
            'free_zone': free_zone,
            'plate_number': normalized_plate,
            'user': None,
            'wallet_balance': None,
            **session_fields,
            'is_active': None,
            'is_primary': None,
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOperator])
def reset_season(request):
    """
    Start a new operational season.

    POST /api/parking/season/reset/
    """
    if request.user.role not in ['operator', 'admin']:
        return Response(
            {'error': 'Operator access required'},
            status=status.HTTP_403_FORBIDDEN,
        )

    state, closed_sessions, deleted_detection_fails = reset_operational_season(
        request.user
    )

    return Response(
        {
            'season_started_at': state.season_started_at.isoformat(),
            'reset_count': state.reset_count,
            'closed_sessions': closed_sessions,
            'deleted_detection_fails': deleted_detection_fails,
        },
        status=status.HTTP_200_OK,
    )


def _parse_decimal(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def ingest_detection_fail(request):
    """
    Core → Django ingest of a captured detection fail.

    POST /api/parking/detection-fails/ingest/
    Auth: header X-Fail-Ingest-Token
    """
    expected = getattr(settings, 'DETECTION_FAIL_INGEST_TOKEN', '') or ''
    provided = request.headers.get('X-Fail-Ingest-Token', '')
    if not expected or provided != expected:
        return Response(
            {'error': 'Invalid ingest token'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    capture_id = request.data.get('capture_id')
    fail_type = request.data.get('fail_type')
    if not capture_id or not fail_type:
        return Response(
            {'error': 'capture_id and fail_type are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if fail_type not in dict(DetectionFail.FAIL_TYPE_CHOICES):
        return Response(
            {'error': f'Invalid fail_type: {fail_type}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    bbox_raw = request.data.get('bbox')
    bbox = None
    if bbox_raw not in (None, '', 'null'):
        if isinstance(bbox_raw, (list, dict)):
            bbox = bbox_raw
        else:
            try:
                bbox = json.loads(bbox_raw)
            except (TypeError, json.JSONDecodeError):
                bbox = None

    direction = (request.data.get('direction') or 'entry').strip().lower()
    if direction not in ('entry', 'exit'):
        camera_id = (request.data.get('camera_id') or '').lower()
        direction = 'exit' if 'exit' in camera_id else 'entry'

    captured_at = None
    ts = request.data.get('timestamp')
    if ts:
        captured_at = parse_datetime(str(ts))

    has_scene_b_raw = str(request.data.get('has_scene_b', '')).strip().lower()
    has_scene_b = has_scene_b_raw in ('1', 'true', 'yes')

    defaults = {
        'fail_type': fail_type,
        'raw_ocr': (request.data.get('raw_ocr') or '')[:64],
        'validation_error': (request.data.get('validation_error') or '')[:512],
        'plate_confidence': _parse_decimal(request.data.get('plate_confidence')),
        'char_confidence': _parse_decimal(request.data.get('char_confidence')),
        'bbox': bbox,
        'camera_id': (request.data.get('camera_id') or '')[:32],
        'direction': direction,
        'local_data_path': (request.data.get('local_data_path') or '')[:512],
        'sharpness': (
            float(request.data['sharpness'])
            if request.data.get('sharpness') not in (None, '')
            else None
        ),
        'has_scene_b': has_scene_b,
        'scene_b_source': (request.data.get('scene_b_source') or '')[:32],
        'captured_at': captured_at,
        'review_status': 'pending',
        'not_a_plate': False,
    }

    obj, created = DetectionFail.objects.update_or_create(
        id=capture_id,
        defaults=defaults,
    )

    full_image = request.FILES.get('full_image')
    crop_image = request.FILES.get('crop_image')
    scene_b_image = request.FILES.get('scene_b_image')
    update_fields = []
    if full_image:
        obj.full_image = full_image
        update_fields.append('full_image')
    if crop_image:
        obj.crop_image = crop_image
        update_fields.append('crop_image')
    if scene_b_image:
        obj.scene_b_image = scene_b_image
        obj.has_scene_b = True
        update_fields.extend(['scene_b_image', 'has_scene_b'])
    if update_fields:
        obj.save(update_fields=list(dict.fromkeys(update_fields)))

    logger.info(
        'Ingested DetectionFail %s (%s) created=%s',
        obj.id,
        fail_type,
        created,
    )

    fail_id = obj.id

    def _enqueue_fail():
        try:
            from .models import DetectionFail
            from .sync_outbox import enqueue_detection_fail

            fail = DetectionFail.objects.filter(pk=fail_id).first()
            if fail:
                enqueue_detection_fail(fail)
        except Exception:
            logger.exception('Outbox enqueue after detection-fail ingest failed %s', fail_id)

    from django.db import transaction as _tx

    _tx.on_commit(_enqueue_fail)

    return Response(
        {
            'success': True,
            'created': created,
            'id': str(obj.id),
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOperator])
def list_detection_fails(request):
    """
    GET /api/parking/detection-fails/?status=pending&date=YYYY-MM-DD&offset=0&limit=50

    Filters by capture day (Asia/Tehran) using captured_at, falling back to created_at.
    """
    from django.db.models import DateTimeField
    from django.db.models.functions import Coalesce

    from utils.tehran_dates import date_range_tehran, parse_date_param

    requested_date, err = parse_date_param(
        request, required=False, default_today=True
    )
    if err is not None:
        return err

    day_start, day_end = date_range_tehran(requested_date)
    qs = (
        DetectionFail.objects.all()
        .annotate(
            event_at=Coalesce(
                'captured_at',
                'created_at',
                output_field=DateTimeField(),
            )
        )
        .filter(event_at__gte=day_start, event_at__lte=day_end)
        .order_by('-event_at')
    )

    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(review_status=status_filter)
    fail_type = request.query_params.get('fail_type')
    if fail_type:
        qs = qs.filter(fail_type=fail_type)

    try:
        offset = max(int(request.query_params.get('offset', 0)), 0)
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = min(max(int(request.query_params.get('limit', 50)), 1), 200)
    except (TypeError, ValueError):
        limit = 50

    total = qs.count()
    page = list(qs[offset : offset + limit])
    results = [serialize_detection_fail(f, request) for f in page]
    return Response(
        {
            'count': total,
            'results': results,
            'offset': offset,
            'limit': limit,
            'has_more': offset + len(results) < total,
            'date': requested_date.isoformat(),
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOperator])
def get_detection_fail(request, fail_id):
    """GET /api/parking/detection-fails/<uuid>/"""
    fail = get_object_or_404(DetectionFail, pk=fail_id)
    return Response(serialize_detection_fail(fail, request))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOperator])
@parser_classes([JSONParser])
def review_detection_fail(request, fail_id):
    """
    POST /api/parking/detection-fails/<uuid>/review/

    Body: { "action": "correct"|"not_a_plate", "plate_confirmed": "..." }
    """
    if request.user.role not in ['operator', 'admin']:
        return Response(
            {'error': 'Operator access required'},
            status=status.HTTP_403_FORBIDDEN,
        )

    fail = get_object_or_404(DetectionFail, pk=fail_id)
    action = (request.data.get('action') or '').strip().lower()

    try:
        if action == 'correct':
            plate_confirmed = request.data.get('plate_confirmed', '')
            if not plate_confirmed:
                return Response(
                    {'error': 'plate_confirmed is required'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            result = review_correct(
                detection_fail=fail,
                operator_id=request.user.id,
                plate_confirmed=plate_confirmed,
            )
            return Response(result, status=status.HTTP_200_OK)

        if action in ('not_a_plate', 'reject'):
            result = review_not_a_plate(
                detection_fail=fail,
                operator_id=request.user.id,
            )
            return Response(result, status=status.HTTP_200_OK)

        return Response(
            {'error': 'action must be "correct" or "not_a_plate"'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOperator])
def detection_fail_metrics(request):
    """GET /api/parking/detection-fails/metrics/ — Django-side review counters."""
    from django.db.models import Count

    by_status = {
        row['review_status']: row['c']
        for row in DetectionFail.objects.values('review_status').annotate(c=Count('id'))
    }
    by_type = {
        row['fail_type']: row['c']
        for row in DetectionFail.objects.values('fail_type').annotate(c=Count('id'))
    }
    return Response(
        {
            'pending': by_status.get('pending', 0),
            'corrected': by_status.get('corrected', 0),
            'not_a_plate': by_status.get('not_a_plate', 0),
            'by_status': by_status,
            'by_fail_type': by_type,
            'operator_corrected_plate': by_status.get('corrected', 0),
            'operator_marked_not_plate': by_status.get('not_a_plate', 0),
            'operator_confirmed_miss': by_type.get('operator_confirmed_miss', 0),
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsOperator])
def sync_status(request):
    """GET /api/parking/sync/status/ — local outbox health (cloud replica push)."""
    from django.conf import settings

    from .models import EventMedia, SyncOutbox, SyncState
    from .sync_outbox import refresh_sync_state

    state = refresh_sync_state()
    dead = list(
        SyncOutbox.objects.filter(status='dead_letter')
        .order_by('-updated_at')
        .values('id', 'payload_type', 'payload_uuid', 'attempts', 'last_error', 'updated_at')[:50]
    )
    return Response(
        {
            'cloud_sync_enabled': bool(getattr(settings, 'CLOUD_SYNC_ENABLED', False)),
            'site_id': getattr(settings, 'CLOUD_SITE_ID', ''),
            'last_success_at': state.last_success_at,
            'last_error_at': state.last_error_at,
            'last_error': state.last_error,
            'pending_metadata_count': state.pending_metadata_count,
            'pending_image_count': state.pending_image_count,
            'dead_letter_count': state.dead_letter_count,
            'images_pending_upload': EventMedia.objects.filter(
                upload_status__in=('pending', 'failed')
            ).count(),
            'dead_letters': dead,
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsOperator])
def sync_requeue(request):
    """POST /api/parking/sync/requeue/ — requeue dead-letter outbox rows."""
    from .sync_outbox import refresh_sync_state, requeue_dead_letters

    ids = request.data.get('ids')
    count = requeue_dead_letters(ids)
    refresh_sync_state()
    return Response({'requeued': count})

