"""
Wallet service for balance operations and transaction management.

This module provides the WalletService class for managing wallet balances,
top-ups, fee deductions, and balance checks with atomic database operations.

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 18.1, 18.2, 18.7, 52.1, 52.2
"""

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from decimal import Decimal
from .models import Wallet, WalletTransaction
from accounts.models import User


class InsufficientFundsError(Exception):
    """
    Exception raised when wallet balance is insufficient for a deduction.
    
    Requirement 18.6: WHEN the wallet balance is insufficient, 
    THE Backend SHALL not deduct any amount.
    """
    pass


class WalletService:
    """
    Service class for wallet balance operations.
    
    Provides methods for:
    - Getting wallet balance
    - Top-up operations with transaction recording
    - Fee deductions with atomicity
    - Balance sufficiency checks
    
    All balance-modifying operations use database transactions for atomicity.
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 18.1, 18.2, 18.7, 52.1, 52.2
    """
    
    @staticmethod
    def get_balance(user_id: int) -> int:
        """
        Get the current wallet balance for a user.
        
        Args:
            user_id: The ID of the user whose balance to retrieve
            
        Returns:
            Current balance in Toman (integer)
            
        Raises:
            ObjectDoesNotExist: If user or wallet does not exist
            
        Requirement 5.1: WHEN an operator submits a top-up request with valid 
        wallet ID and amount, THE Backend SHALL increase the wallet balance 
        by the specified amount.
        """
        try:
            wallet = Wallet.objects.get(user_id=user_id)
            return int(wallet.balance)
        except Wallet.DoesNotExist:
            raise ObjectDoesNotExist(f"Wallet not found for user_id={user_id}")
    
    @staticmethod
    @transaction.atomic
    def topup(wallet_id: int, amount: int, operator_id: int) -> WalletTransaction:
        """
        Add funds to a wallet and create a transaction record.
        
        This operation is atomic - both the balance update and transaction
        creation succeed or fail together.
        
        Args:
            wallet_id: The ID of the wallet to top up
            amount: The amount to add in Toman (must be positive)
            operator_id: The ID of the operator performing the top-up
            
        Returns:
            The created WalletTransaction record
            
        Raises:
            ValueError: If amount is not positive
            ObjectDoesNotExist: If wallet or operator does not exist
            
        Requirements:
        - 5.1: Increase wallet balance by specified amount
        - 5.2: Create transaction record with type 'topup'
        - 5.3: Record operator's user ID who performed the top-up
        - 5.4: Return updated wallet balance within 1 second
        - 5.5: Reject top-up requests with negative or zero amounts
        - 52.1: Execute wallet deduction and transaction creation in single transaction
        """
        # Validate amount
        if amount <= 0:
            raise ValueError("Top-up amount must be positive")
        
        # Get wallet and operator (will raise ObjectDoesNotExist if not found)
        wallet = Wallet.objects.select_for_update().get(id=wallet_id)
        operator = User.objects.get(id=operator_id)
        
        # Update wallet balance
        wallet.balance = Decimal(wallet.balance) + Decimal(amount)
        wallet.save()
        
        # Create transaction record
        txn = WalletTransaction.objects.create(
            wallet=wallet,
            amount=amount,
            type='topup',
            description=f"Top-up by operator {operator.full_name}",
            performed_by=operator
        )
        
        return txn
    
    @staticmethod
    @transaction.atomic
    def deduct_fee(wallet_id: int, amount: int, session_id: int = None) -> WalletTransaction:
        """
        Deduct a parking fee from a wallet and create a transaction record.
        
        This operation is atomic - both the balance deduction and transaction
        creation succeed or fail together. If the balance is insufficient,
        an InsufficientFundsError is raised and no changes are made.
        
        Args:
            wallet_id: The ID of the wallet to deduct from
            amount: The fee amount to deduct in Toman (must be positive)
            session_id: Optional parking session ID to link to transaction
            
        Returns:
            The created WalletTransaction record
            
        Raises:
            ValueError: If amount is not positive
            InsufficientFundsError: If wallet balance < amount
            ObjectDoesNotExist: If wallet does not exist
            
        Requirements:
        - 18.1: Deduct fee from wallet when session closed for registered user
        - 18.2: Create wallet transaction record with type 'fee' linked to session
        - 18.5: Set session status to 'unpaid' when wallet balance insufficient
        - 18.6: Do not deduct any amount when balance insufficient
        - 18.7: Perform wallet deduction and transaction creation atomically
        - 52.1: Execute in single database transaction
        - 52.2: Update session and create gate event links atomically
        """
        # Validate amount
        if amount <= 0:
            raise ValueError("Fee amount must be positive")
        
        # Get wallet with row-level lock for atomicity
        wallet = Wallet.objects.select_for_update().get(id=wallet_id)
        
        # Check sufficient balance
        if wallet.balance < amount:
            raise InsufficientFundsError(
                f"Insufficient balance: {wallet.balance} < {amount}"
            )
        
        # Deduct fee from wallet
        wallet.balance = Decimal(wallet.balance) - Decimal(amount)
        wallet.save()
        
        txn_kwargs = {
            'wallet': wallet,
            'amount': amount,
            'type': 'fee',
            'description': (
                f'Parking fee for session {session_id}' if session_id else 'Parking fee'
            ),
        }
        if session_id is not None:
            txn_kwargs['session_id'] = session_id

        txn = WalletTransaction.objects.create(**txn_kwargs)
        
        return txn
    
    @staticmethod
    def check_sufficient_balance(user_id: int, required_amount: int) -> bool:
        """
        Check if a user's wallet has sufficient balance for a required amount.
        
        Args:
            user_id: The ID of the user whose balance to check
            required_amount: The amount required in Toman
            
        Returns:
            True if balance >= required_amount, False otherwise
            
        Raises:
            ObjectDoesNotExist: If user or wallet does not exist
            
        Requirement 18.5: WHEN the wallet balance is insufficient, 
        THE Backend SHALL set the session status to 'unpaid'.
        """
        try:
            wallet = Wallet.objects.get(user_id=user_id)
            return wallet.balance >= required_amount
        except Wallet.DoesNotExist:
            raise ObjectDoesNotExist(f"Wallet not found for user_id={user_id}")
