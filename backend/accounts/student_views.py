"""
Student mobile app authentication: OTP (dev), registration, profile.
"""

import random
import re
import secrets

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from plates.models import Plate
from utils.plate_normalizer import normalize_plate
from parking.models import ParkingSession
from wallets.models import WalletTransaction

from .models import User

OTP_CACHE_PREFIX = 'student_otp:'
VERIFY_CACHE_PREFIX = 'student_verify:'
OTP_TTL_SECONDS = 300
VERIFY_TTL_SECONDS = 600


def normalize_phone(phone: str) -> str:
    """Normalize Iranian mobile to +98XXXXXXXXXX."""
    digits = re.sub(r'\D', '', phone or '')
    if digits.startswith('98') and len(digits) >= 12:
        return '+' + digits
    if digits.startswith('0') and len(digits) == 11:
        return '+98' + digits[1:]
    if len(digits) == 10 and digits.startswith('9'):
        return '+98' + digits
    if phone and phone.startswith('+'):
        return phone
    return '+' + digits if digits else phone


def _otp_key(phone: str) -> str:
    return f'{OTP_CACHE_PREFIX}{phone}'


def _issue_tokens(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': _serialize_student(user),
    }


def _serialize_student(user: User) -> dict:
    wallet_balance = None
    try:
        wallet_balance = int(user.wallet.balance)
    except Exception:
        pass

    plates = list(
        user.plates.filter(is_active=True).values(
            'id', 'plate_number', 'is_primary', 'is_verified', 
            'is_free_zone', 'free_zone'
        )
    )
    return {
        'id': user.id,
        'full_name': user.full_name,
        'phone': user.phone,
        'student_id': user.student_id,
        'wallet_balance': wallet_balance,
        'plates': plates,
        'profile_complete': bool(user.full_name and plates),
    }


class StudentSendOtpView(APIView):
    """
    POST /api/auth/student/otp/send/
    Body: { "phone": "09123456789" }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        phone = normalize_phone(request.data.get('phone', '').strip())
        if not phone or len(re.sub(r'\D', '', phone)) < 10:
            return Response({'error': 'شماره موبایل معتبر نیست'}, status=status.HTTP_400_BAD_REQUEST)

        code = f'{random.randint(100000, 999999)}'
        cache.set(_otp_key(phone), code, OTP_TTL_SECONDS)

        payload = {
            'success': True,
            'message': 'کد تأیید ارسال شد',
            'phone': phone,
            'expires_in': OTP_TTL_SECONDS,
        }
        if settings.DEBUG:
            payload['debug_otp'] = code

        return Response(payload)


class StudentVerifyOtpView(APIView):
    """
    POST /api/auth/student/otp/verify/
    Body: { "phone": "...", "code": "123456" }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        phone = normalize_phone(request.data.get('phone', '').strip())
        code = (request.data.get('code') or '').strip()

        if not phone or not code:
            return Response({'error': 'شماره و کد الزامی است'}, status=status.HTTP_400_BAD_REQUEST)

        cached = cache.get(_otp_key(phone))
        if not cached or str(cached) != str(code):
            return Response({'error': 'کد نامعتبر یا منقضی شده'}, status=status.HTTP_400_BAD_REQUEST)

        cache.delete(_otp_key(phone))

        try:
            user = User.objects.get(phone=phone, role='student')
            return Response({
                'verified': True,
                'is_existing_user': True,
                'profile_complete': bool(user.plates.filter(is_active=True).exists()),
                **_issue_tokens(user),
            })
        except User.DoesNotExist:
            verification_token = secrets.token_urlsafe(32)
            cache.set(f'{VERIFY_CACHE_PREFIX}{verification_token}', phone, VERIFY_TTL_SECONDS)
            return Response({
                'verified': True,
                'is_existing_user': False,
                'verification_token': verification_token,
                'message': 'لطفاً نام و پلاک خود را ثبت کنید',
            })


class StudentRegisterView(APIView):
    """
    POST /api/auth/student/register/
    Body: { "verification_token", "full_name", "plate_number", "student_id"? }
    """

    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        token = request.data.get('verification_token', '').strip()
        full_name = (request.data.get('full_name') or '').strip()
        plate_raw = (request.data.get('plate_number') or '').strip()
        student_id = (request.data.get('student_id') or '').strip() or None

        if not token:
            return Response({'error': 'verification_token الزامی است'}, status=status.HTTP_400_BAD_REQUEST)
        if not full_name:
            return Response({'error': 'نام الزامی است'}, status=status.HTTP_400_BAD_REQUEST)
        if not plate_raw:
            return Response({'error': 'شماره پلاک الزامی است'}, status=status.HTTP_400_BAD_REQUEST)

        phone = cache.get(f'{VERIFY_CACHE_PREFIX}{token}')
        if not phone:
            return Response(
                {'error': 'توکن ثبت‌نام منقضی شده. دوباره OTP بگیرید'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            normalized_result = normalize_plate(plate_raw, free_zone=None)
            
            # Check if it's a Free Zone plate (returns tuple) or national plate (returns string)
            if isinstance(normalized_result, tuple):
                plate_number, free_zone = normalized_result
                is_free_zone = True
            else:
                plate_number = normalized_result
                free_zone = None
                is_free_zone = False
        except ValueError as e:
            error_msg = str(e)
            # If it's an ambiguity error, provide helpful guidance
            if 'Ambiguous plate format' in error_msg:
                return Response(
                    {'error': 'فرمت پلاک مبهم است. لطفاً از فرمت API استفاده کنید (مثال: 17243FZKISH66)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(phone=phone).exists():
            return Response({'error': 'این شماره قبلاً ثبت شده'}, status=status.HTTP_400_BAD_REQUEST)

        if Plate.objects.filter(plate_number=plate_number, is_active=True).exists():
            return Response({'error': 'این پلاک قبلاً ثبت شده است'}, status=status.HTTP_400_BAD_REQUEST)

        if student_id and User.objects.filter(student_id=student_id).exists():
            return Response({'error': 'شماره دانشجویی تکراری است'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            phone=phone,
            password=secrets.token_urlsafe(16),
            full_name=full_name,
            student_id=student_id,
            role='student',
        )
        
        # Create plate with Free Zone support
        plate = Plate(
            user=user,
            plate_number=plate_number,
            is_primary=True,
            is_verified=False,
        )
        
        if is_free_zone:
            plate.is_free_zone = True
            plate.free_zone = free_zone
        
        plate.save()

        cache.delete(f'{VERIFY_CACHE_PREFIX}{token}')

        return Response({
            'success': True,
            'message': 'ثبت‌نام با موفقیت انجام شد',
            **_issue_tokens(user),
        }, status=status.HTTP_201_CREATED)


class StudentMeView(APIView):
    """GET /api/auth/student/me/ — current student profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'student':
            return Response({'error': 'فقط دانشجو'}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_student(request.user))


class StudentAddPlateView(APIView):
    """
    POST /api/auth/student/plates/add/
    Body: { "plate_number": "12ب34567" or "17243FZMAKU66" }
    """

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        if request.user.role != 'student':
            return Response({'error': 'فقط دانشجو'}, status=status.HTTP_403_FORBIDDEN)

        plate_raw = (request.data.get('plate_number') or '').strip()

        if not plate_raw:
            return Response({'error': 'شماره پلاک الزامی است'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            normalized_result = normalize_plate(plate_raw, free_zone=None)
            
            # Check if it's a Free Zone plate (returns tuple) or national plate (returns string)
            if isinstance(normalized_result, tuple):
                plate_number, free_zone = normalized_result
                is_free_zone = True
            else:
                plate_number = normalized_result
                free_zone = None
                is_free_zone = False
        except ValueError as e:
            error_msg = str(e)
            return Response({'error': f'فرمت پلاک نامعتبر: {error_msg}'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if plate already exists
        if Plate.objects.filter(plate_number=plate_number, is_active=True).exists():
            return Response({'error': 'این پلاک قبلاً ثبت شده است'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if user already has 5 plates (limit)
        if request.user.plates.filter(is_active=True).count() >= 5:
            return Response({'error': 'حداکثر ۵ پلاک می‌توانید ثبت کنید'}, status=status.HTTP_400_BAD_REQUEST)

        # Create plate
        is_first_plate = not request.user.plates.filter(is_active=True).exists()
        
        plate = Plate(
            user=request.user,
            plate_number=plate_number,
            is_primary=is_first_plate,  # First plate is primary
            is_verified=False,
        )
        
        if is_free_zone:
            plate.is_free_zone = True
            plate.free_zone = free_zone
        
        plate.save()

        return Response({
            'success': True,
            'message': 'پلاک با موفقیت ثبت شد',
            'plate': {
                'id': plate.id,
                'plate_number': plate.plate_number,
                'is_free_zone': plate.is_free_zone,
                'free_zone': plate.free_zone,
                'is_primary': plate.is_primary,
                'is_verified': plate.is_verified,
            },
        }, status=status.HTTP_201_CREATED)



class StudentParkingSessionsView(APIView):
    """
    GET /api/auth/student/sessions/ — list student's parking sessions
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'student':
            return Response({'error': 'فقط دانشجو'}, status=status.HTTP_403_FORBIDDEN)

        # Get all user's plates
        user_plates = request.user.plates.filter(is_active=True).values_list('id', flat=True)

        # Get sessions for user's plates
        sessions = ParkingSession.objects.filter(
            plate_id__in=user_plates
        ).select_related('plate').order_by('-entry_time')[:50]  # Last 50 sessions

        sessions_data = []
        for session in sessions:
            sessions_data.append({
                'id': session.id,
                'plate_number': session.plate.plate_number if session.plate else session.guest_plate_number,
                'is_free_zone': session.plate.is_free_zone if session.plate else False,
                'free_zone': session.plate.free_zone if session.plate else None,
                'entry_time': session.entry_time.isoformat(),
                'exit_time': session.exit_time.isoformat() if session.exit_time else None,
                'duration_minutes': session.duration_minutes,
                'fee_charged': float(session.fee_charged) if session.fee_charged else 0,
                'status': session.status,
                'payment_method': session.payment_method,
            })

        return Response({
            'count': len(sessions_data),
            'sessions': sessions_data,
        })


class StudentWalletTransactionsView(APIView):
    """
    GET /api/auth/student/wallet/transactions/ — list student's wallet transactions
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'student':
            return Response({'error': 'فقط دانشجو'}, status=status.HTTP_403_FORBIDDEN)

        try:
            wallet = request.user.wallet
        except Exception:
            return Response({
                'count': 0,
                'transactions': [],
            })

        # Get transactions
        transactions = WalletTransaction.objects.filter(
            wallet=wallet
        ).select_related('session', 'session__plate').order_by('-created_at')[:100]  # Last 100 transactions

        transactions_data = []
        for txn in transactions:
            plate_number = None
            is_free_zone = False
            free_zone = None
            
            if txn.session and txn.session.plate:
                plate_number = txn.session.plate.plate_number
                is_free_zone = txn.session.plate.is_free_zone
                free_zone = txn.session.plate.free_zone
            elif txn.session and txn.session.guest_plate_number:
                plate_number = txn.session.guest_plate_number

            transactions_data.append({
                'id': txn.id,
                'amount': int(txn.amount),
                'type': txn.type,
                'description': txn.description,
                'created_at': txn.created_at.isoformat(),
                'session_id': txn.session_id,
                'plate_number': plate_number,
                'is_free_zone': is_free_zone,
                'free_zone': free_zone,
            })

        return Response({
            'count': len(transactions_data),
            'transactions': transactions_data,
            'current_balance': int(wallet.balance),
        })
