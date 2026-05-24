"""
Parking session service for managing parking session lifecycle.

This module provides the ParkingSessionService class for creating entry sessions,
closing exit sessions with fee calculation and payment processing, recording cash
payments, and waiving fees.

Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7,
             19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 20.1, 20.2, 20.3, 20.4, 20.5,
             80.1, 80.2, 80.3, 80.4, 80.5
"""

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone
from decimal import Decimal
from typing import Dict, Optional

from .models import GateEvent, ParkingSession
from .plate_utils import (
    find_active_parked_session,
    find_plate_record,
    link_session_to_plate,
    normalize_plate_strict,
)
from plates.models import Plate
from wallets.services import WalletService, InsufficientFundsError
from utils.fee_calculator import calculate_fee


class ParkingSessionService:
    """
    Service class for parking session lifecycle management.
    
    Provides methods for:
    - Creating entry sessions
    - Closing exit sessions with fee calculation and wallet payment
    - Recording cash payments for unpaid sessions
    - Waiving fees for special cases
    - Preventing concurrent sessions for the same plate
    
    All session-modifying operations use database transactions for atomicity.
    
    Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7,
                 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 20.1, 20.2, 20.3, 20.4, 20.5,
                 80.1, 80.2, 80.3, 80.4, 80.5
    """
    
    @staticmethod
    @transaction.atomic
    def create_entry_session(gate_event: GateEvent) -> ParkingSession:
        """
        Create a new parking session when a vehicle enters.
        
        This method:
        1. Checks for concurrent sessions with status='parked' for the same plate
        2. Auto-closes any existing 'parked' session before creating new one
        3. Creates a new session with status='parked'
        4. Links to plate_id if registered, else stores guest_plate_number
        5. Records entry event and entry timestamp
        
        Args:
            gate_event: The entry gate event that triggered session creation
            
        Returns:
            The created ParkingSession
            
        Raises:
            ValidationError: If gate_event direction is not 'entry'
            
        Requirements:
        - 15.1: Create parking session when entry gate event is approved
        - 15.2: Record entry event ID and entry timestamp
        - 15.3: Link session to plate_id if registered
        - 15.4: Store guest_plate_number if unregistered
        - 15.5: Set session status to 'parked'
        - 15.6: Leave exit_event_id and exit_time as null
        - 15.7: Return created session ID within 1 second
        - 80.1: Check for concurrent sessions
        - 80.2: Auto-close previous session if exists
        """
        # Validate gate event direction
        if gate_event.direction != 'entry':
            raise ValidationError("Gate event must be an entry event")
        
        plate_number = gate_event.plate_confirmed or gate_event.plate_raw
        normalized_plate = plate_number
        if plate_number:
            try:
                normalized_plate = normalize_plate_strict(plate_number)
            except ValueError:
                normalized_plate = plate_number

        matched_plate = gate_event.matched_plate
        if not matched_plate and normalized_plate:
            matched_plate = find_plate_record(normalized_plate)
            if matched_plate:
                gate_event.matched_plate = matched_plate
                gate_event.matched_user = matched_plate.user
                GateEvent.objects.filter(pk=gate_event.pk).update(
                    matched_plate=matched_plate,
                    matched_user=matched_plate.user,
                )

        if normalized_plate:
            while True:
                existing_session = find_active_parked_session(
                    normalized_plate,
                    matched_plate=matched_plate,
                )
                if not existing_session:
                    break
                existing_session.status = 'flagged'
                existing_session.notes = (
                    f"Auto-closed due to new entry without exit. "
                    f"Original entry: {existing_session.entry_time}"
                )
                existing_session.save()
        
        # Create new parking session
        # Requirements 15.1-15.7
        session = ParkingSession.objects.create(
            plate=matched_plate,
            guest_plate_number=None if matched_plate else normalized_plate,
            entry_event=gate_event,
            entry_time=gate_event.created_at,
            status='parked',
        )
        
        # Link gate event to session
        # Use update() to bypass immutability check since we're only linking, not modifying audit data
        GateEvent.objects.filter(pk=gate_event.pk).update(session=session)
        
        return session
    
    @staticmethod
    @transaction.atomic
    def close_exit_session(gate_event: GateEvent) -> Dict:
        """
        Close a parking session when a vehicle exits.
        
        This method:
        1. Finds the active session for the plate
        2. Calculates parking duration and fee
        3. Attempts wallet payment if registered user with sufficient balance
        4. Sets status to 'completed' if payment succeeds, 'unpaid' if insufficient
        5. Records exit event and exit timestamp
        
        Args:
            gate_event: The exit gate event that triggered session closure
            
        Returns:
            Dictionary containing:
            - session: The closed ParkingSession
            - fee: The calculated fee in Toman
            - payment_status: 'completed', 'unpaid', or 'no_session'
            - wallet_sufficient: Boolean indicating if wallet had sufficient balance
            
        Raises:
            ValidationError: If gate_event direction is not 'exit'
            
        Requirements:
        - 17.1: Close parking session when exit gate event approved
        - 17.2: Record exit event ID and exit timestamp
        - 17.3: Calculate parking duration in minutes
        - 17.4: Calculate parking fee using fee calculation rules
        - 17.5: Update session status based on payment outcome
        - 17.6: Link exit gate event to closed session
        - 17.7: Return calculated fee and session details within 1 second
        - 18.1: Deduct fee from wallet if sufficient balance
        - 18.2: Create wallet transaction with type 'fee'
        - 18.3: Set payment_method to 'wallet'
        - 18.4: Set status to 'completed' on successful payment
        - 18.5: Set status to 'unpaid' if insufficient balance
        - 18.6: Do not deduct any amount if insufficient
        - 18.7: Perform wallet deduction and transaction atomically
        """
        # Validate gate event direction
        if gate_event.direction != 'exit':
            raise ValidationError("Gate event must be an exit event")
        
        plate_number = gate_event.plate_confirmed or gate_event.plate_raw
        normalized_plate = None
        if plate_number:
            try:
                normalized_plate = normalize_plate_strict(plate_number)
            except ValueError:
                normalized_plate = plate_number

        if not normalized_plate:
            return {
                'session': None,
                'fee': 0,
                'payment_status': 'no_session',
                'wallet_sufficient': False,
            }

        matched_plate = gate_event.matched_plate or find_plate_record(normalized_plate)
        session = find_active_parked_session(
            normalized_plate,
            matched_plate=matched_plate,
        )

        if not session:
            return {
                'session': None,
                'fee': 0,
                'payment_status': 'no_session',
                'wallet_sufficient': False,
            }

        if matched_plate and session.plate_id is None:
            session = link_session_to_plate(session, matched_plate)
        elif matched_plate and session.plate_id != matched_plate.id:
            session = link_session_to_plate(session, matched_plate)
        
        # Record exit information
        # Requirements 17.2, 17.3
        session.exit_event = gate_event
        session.exit_time = gate_event.created_at
        
        # Calculate duration in minutes
        duration_seconds = (session.exit_time - session.entry_time).total_seconds()
        session.duration_minutes = int(duration_seconds // 60)
        
        # Calculate fee
        # Requirement 17.4
        if session.plate_id:
            session.plate.refresh_from_db()
        is_student = (
            session.plate is not None
            and session.plate.user.role == 'student'
        )
        fee = calculate_fee(
            entry_time=session.entry_time,
            exit_time=session.exit_time,
            is_student=is_student
        )
        session.fee_charged = Decimal(fee)
        
        # Attempt wallet payment if registered user
        wallet_sufficient = False
        payment_status = 'unpaid'
        
        if session.plate and session.plate.user:
            # Registered user - attempt wallet payment
            user = session.plate.user
            
            try:
                # Check if wallet has sufficient balance
                wallet_sufficient = WalletService.check_sufficient_balance(
                    user_id=user.id,
                    required_amount=fee
                )
                
                if wallet_sufficient and fee > 0:
                    # Deduct fee from wallet
                    # Requirements 18.1, 18.2, 18.7
                    WalletService.deduct_fee(
                        wallet_id=user.wallet.id,
                        amount=fee,
                        session_id=session.id
                    )
                    
                    # Set payment method and status
                    # Requirements 18.3, 18.4
                    session.payment_method = 'wallet'
                    session.status = 'completed'
                    payment_status = 'completed'
                elif fee == 0:
                    # No fee charged (grace period)
                    session.payment_method = 'wallet'
                    session.status = 'completed'
                    payment_status = 'completed'
                    wallet_sufficient = True
                else:
                    # Insufficient balance
                    # Requirements 18.5, 18.6
                    session.status = 'unpaid'
                    payment_status = 'unpaid'
                    
            except (ObjectDoesNotExist, InsufficientFundsError):
                # Wallet not found or insufficient funds
                # Requirements 18.5, 18.6
                session.status = 'unpaid'
                payment_status = 'unpaid'
        else:
            # Guest user - set status to unpaid
            session.status = 'unpaid'
            payment_status = 'unpaid'
        
        # Save session
        # Requirement 17.5
        session.save()
        
        # Link gate event to session
        # Use update() to bypass immutability check since we're only linking, not modifying audit data
        GateEvent.objects.filter(pk=gate_event.pk).update(session=session)
        
        # Return session details
        # Requirement 17.7
        return {
            'session': session,
            'fee': fee,
            'payment_status': payment_status,
            'wallet_sufficient': wallet_sufficient
        }
    
    @staticmethod
    @transaction.atomic
    def record_cash_payment(
        session_id: int,
        operator_id: int,
        notes: Optional[str] = None
    ) -> ParkingSession:
        """
        Record a cash payment for an unpaid parking session.
        
        This method:
        1. Validates that session status is 'unpaid'
        2. Updates status to 'completed'
        3. Sets payment_method to 'cash'
        4. Records operator who collected the cash
        5. Records optional notes
        
        Args:
            session_id: The ID of the session to mark as paid
            operator_id: The ID of the operator collecting the cash
            notes: Optional notes about the payment
            
        Returns:
            The updated ParkingSession
            
        Raises:
            ObjectDoesNotExist: If session or operator not found
            ValidationError: If session status is not 'unpaid'
            
        Requirements:
        - 19.1: Update session status to 'completed'
        - 19.2: Set payment_method to 'cash'
        - 19.3: Record operator user ID who collected cash
        - 19.4: Record optional notes provided by operator
        - 19.5: Validate session status is 'unpaid' before accepting
        - 19.6: Return confirmation within 1 second
        """
        # Get session and operator
        try:
            session = ParkingSession.objects.select_for_update().get(id=session_id)
        except ParkingSession.DoesNotExist:
            raise ObjectDoesNotExist(f"Session with id={session_id} not found")
        
        # Validate session status
        # Requirement 19.5
        if session.status != 'unpaid':
            raise ValidationError(
                f"Cannot record cash payment for session with status '{session.status}'. "
                f"Session must have status 'unpaid'."
            )
        
        # Update session
        # Requirements 19.1, 19.2, 19.3, 19.4
        session.status = 'completed'
        session.payment_method = 'cash'
        session.collected_by_id = operator_id
        
        if notes:
            if session.notes:
                session.notes += f"\n\nCash payment: {notes}"
            else:
                session.notes = f"Cash payment: {notes}"
        
        session.save()
        
        return session
    
    @staticmethod
    @transaction.atomic
    def waive_fee(session_id: int, operator_id: int) -> ParkingSession:
        """
        Waive the parking fee for a session.
        
        This method:
        1. Validates that session status is 'parked' or 'unpaid'
        2. Sets fee_charged to zero
        3. Sets status to 'waived'
        4. Sets payment_method to 'waived'
        5. Records operator who approved the waiver
        
        Args:
            session_id: The ID of the session to waive
            operator_id: The ID of the operator approving the waiver
            
        Returns:
            The updated ParkingSession
            
        Raises:
            ObjectDoesNotExist: If session or operator not found
            ValidationError: If session status is not 'parked' or 'unpaid'
            
        Requirements:
        - 20.1: Set fee_charged to zero
        - 20.2: Set status to 'waived'
        - 20.3: Set payment_method to 'waived'
        - 20.4: Record operator user ID who approved waiver
        - 20.5: Allow waiving fees for sessions in 'parked' or 'unpaid' status
        """
        # Get session
        try:
            session = ParkingSession.objects.select_for_update().get(id=session_id)
        except ParkingSession.DoesNotExist:
            raise ObjectDoesNotExist(f"Session with id={session_id} not found")
        
        # Validate session status
        # Requirement 20.5
        if session.status not in ['parked', 'unpaid']:
            raise ValidationError(
                f"Cannot waive fee for session with status '{session.status}'. "
                f"Session must have status 'parked' or 'unpaid'."
            )
        
        # Update session
        # Requirements 20.1, 20.2, 20.3, 20.4
        session.fee_charged = Decimal(0)
        session.status = 'waived'
        session.payment_method = 'waived'
        session.collected_by_id = operator_id
        
        session.save()
        
        return session
