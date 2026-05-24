"""
Student wallet endpoints (demo top-up for testing).
"""

from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Wallet, WalletTransaction

DEMO_TOPUP_AMOUNT = 100_000


class StudentDemoTopupView(APIView):
    """
    POST /api/wallets/student/demo-topup/
    Adds 100,000 Toman to the authenticated student's wallet (testing only).
    """

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        user = request.user
        if user.role != 'student':
            return Response({'error': 'فقط دانشجو'}, status=status.HTTP_403_FORBIDDEN)

        wallet = Wallet.objects.select_for_update().get(user=user)
        wallet.balance = Decimal(wallet.balance) + Decimal(DEMO_TOPUP_AMOUNT)
        wallet.save()

        WalletTransaction.objects.create(
            wallet=wallet,
            amount=DEMO_TOPUP_AMOUNT,
            type='topup',
            description='شارژ آزمایشی پنل دانشجو',
            performed_by=None,
        )

        return Response({
            'success': True,
            'amount_added': DEMO_TOPUP_AMOUNT,
            'wallet_balance': int(wallet.balance),
            'message': f'{DEMO_TOPUP_AMOUNT:,} تومان به کیف پول اضافه شد',
        })
