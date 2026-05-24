"""
Operator wallet endpoints (cabin cash top-up).
"""

from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsOperatorOrAdmin
from plates.models import Plate
from utils.plate_normalizer import normalize_plate

from .models import Wallet
from .services import WalletService


class OperatorTopupByPlateView(APIView):
    """
    POST /api/wallets/operator/topup-by-plate/

    Body: { "plate": "12 ب 345 17", "amount": 50000 }
    """

    permission_classes = [IsAuthenticated, IsOperatorOrAdmin]

    def post(self, request):
        plate_raw = (request.data.get('plate') or '').strip()
        amount_raw = request.data.get('amount')

        if not plate_raw:
            return Response(
                {'error': 'plate is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount = int(amount_raw)
        except (TypeError, ValueError):
            return Response(
                {'error': 'amount must be a positive integer (Toman)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount <= 0:
            return Response(
                {'error': 'amount must be greater than zero'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            normalized = normalize_plate(plate_raw)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            plate = Plate.objects.select_related('user', 'user__wallet').get(
                plate_number=normalized,
                is_active=True,
            )
        except Plate.DoesNotExist:
            return Response(
                {'error': 'پلاک ثبت‌شده یافت نشد'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            wallet = plate.user.wallet
        except (Wallet.DoesNotExist, AttributeError):
            return Response(
                {'error': 'کیف پول برای این کاربر یافت نشد'},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            txn = WalletService.topup(
                wallet_id=wallet.id,
                amount=amount,
                operator_id=request.user.id,
            )
        except ObjectDoesNotExist:
            return Response(
                {'error': 'کیف پول یا اپراتور یافت نشد'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        wallet.refresh_from_db()

        return Response(
            {
                'success': True,
                'plate_number': plate.plate_number,
                'user_name': plate.user.full_name,
                'wallet_id': wallet.id,
                'amount_added': amount,
                'wallet_balance': int(wallet.balance),
                'transaction_id': txn.id,
                'message': f'{amount:,} تومان به کیف پول اضافه شد',
            },
            status=status.HTTP_200_OK,
        )
