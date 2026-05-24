from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from accounts.models import User
from plates.models import Plate
from .models import GateEvent, ParkingSession


class GateEventModelTest(TestCase):
    """
    Test suite for GateEvent model.
    
    Tests immutability, validation, and basic functionality.
    """
    
    def setUp(self):
        """Set up test data."""
        # Create test user
        self.user = User.objects.create_user(
            phone='+989123456789',
            password='testpass123',
            full_name='Test User',
            role='student'
        )
        
        # Create test operator
        self.operator = User.objects.create_user(
            phone='+989123456790',
            password='testpass123',
            full_name='Test Operator',
            role='operator'
        )
        
        # Create test plate
        self.plate = Plate.objects.create(
            user=self.user,
            plate_number='۱۲ب۳۴۵-۶۷',
            is_primary=True,
            is_active=True
        )
    
    def test_create_entry_gate_event(self):
        """Test creating an entry gate event."""
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_raw='۱۲ب۳۴۵-۶۷',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            confidence_score=Decimal('0.9500'),
            was_edited=False,
            was_auto_approved=False,
            was_rejected=False,
            operator=self.operator,
            matched_user=self.user,
            matched_plate=self.plate
        )
        
        self.assertIsNotNone(gate_event.id)
        self.assertEqual(gate_event.direction, 'entry')
        self.assertEqual(gate_event.plate_confirmed, '۱۲ب۳۴۵-۶۷')
        self.assertEqual(gate_event.operator, self.operator)
        self.assertIsNotNone(gate_event.created_at)
    
    def test_create_exit_gate_event(self):
        """Test creating an exit gate event."""
        gate_event = GateEvent.objects.create(
            camera_id='exit',
            direction='exit',
            plate_raw='۱۲ب۳۴۵-۶۷',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            confidence_score=Decimal('0.8750'),
            was_edited=False,
            was_auto_approved=True,
            was_rejected=False,
            operator=self.operator,
            matched_user=self.user,
            matched_plate=self.plate
        )
        
        self.assertEqual(gate_event.direction, 'exit')
        self.assertTrue(gate_event.was_auto_approved)
    
    def test_gate_event_with_edited_plate(self):
        """Test gate event where operator edited the plate."""
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_raw='۱۲ب۳۴۵-۶۸',  # Wrong detection
            plate_confirmed='۱۲ب۳۴۵-۶۷',  # Corrected by operator
            confidence_score=Decimal('0.6500'),
            was_edited=True,
            was_auto_approved=False,
            was_rejected=False,
            operator=self.operator,
            matched_user=self.user,
            matched_plate=self.plate
        )
        
        self.assertTrue(gate_event.was_edited)
        self.assertNotEqual(gate_event.plate_raw, gate_event.plate_confirmed)
    
    def test_gate_event_rejected(self):
        """Test rejected gate event."""
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_raw='invalid',
            confidence_score=Decimal('0.3000'),
            was_edited=False,
            was_auto_approved=False,
            was_rejected=True,
            operator=self.operator
        )
        
        self.assertTrue(gate_event.was_rejected)
        self.assertIsNone(gate_event.matched_user)
        self.assertIsNone(gate_event.matched_plate)
    
    def test_gate_event_immutability_update(self):
        """Test that gate events cannot be updated."""
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator
        )
        
        # Try to update the gate event
        gate_event.plate_confirmed = '۱۲ب۳۴۵-۶۸'
        
        with self.assertRaises(ValidationError) as context:
            gate_event.save()
        
        self.assertIn('immutable', str(context.exception).lower())
    
    def test_gate_event_immutability_delete(self):
        """Test that gate events cannot be deleted."""
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator
        )
        
        with self.assertRaises(ValidationError) as context:
            gate_event.delete()
        
        self.assertIn('immutable', str(context.exception).lower())
    
    def test_invalid_direction(self):
        """Test that invalid direction raises validation error."""
        gate_event = GateEvent(
            camera_id='entry',
            direction='invalid',  # Invalid direction
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator
        )
        
        with self.assertRaises(ValidationError):
            gate_event.save()
    
    def test_confidence_score_validation(self):
        """Test confidence score must be between 0 and 1."""
        # Test score > 1
        gate_event = GateEvent(
            camera_id='entry',
            direction='entry',
            confidence_score=1.5,  # Invalid: > 1
            operator=self.operator
        )
        
        with self.assertRaises(ValidationError):
            gate_event.save()
        
        # Test score < 0
        gate_event = GateEvent(
            camera_id='entry',
            direction='entry',
            confidence_score=-0.1,  # Invalid: < 0
            operator=self.operator
        )
        
        with self.assertRaises(ValidationError):
            gate_event.save()
    
    def test_gate_event_indexes(self):
        """Test that indexes are created correctly."""
        # Create multiple gate events with different plates
        # Use Persian digits 0-4 for the last digit
        persian_digits = ['۰', '۱', '۲', '۳', '۴']
        for digit in persian_digits:
            GateEvent.objects.create(
                camera_id='entry',
                direction='entry',
                plate_confirmed=f'۱۲ب۳۴۵-۶{digit}',
                operator=self.operator
            )
        
        # Query using indexed fields
        events = GateEvent.objects.filter(plate_confirmed='۱۲ب۳۴۵-۶۰')
        self.assertEqual(events.count(), 1)
        
        # Query using direction and created_at index
        entry_events = GateEvent.objects.filter(direction='entry').order_by('-created_at')
        self.assertEqual(entry_events.count(), 5)
    
    def test_gate_event_string_representation(self):
        """Test the string representation of gate event."""
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator
        )
        
        str_repr = str(gate_event)
        self.assertIn('ورودی', str_repr)  # Entry in Persian
        self.assertIn('۱۲ب۳۴۵-۶۷', str_repr)
    
    def test_gate_event_with_session(self):
        """Test gate event linked to parking session."""
        from django.utils import timezone
        # Create a proper parking session with required fields
        session = ParkingSession.objects.create(
            plate=self.plate,
            entry_time=timezone.now(),
            status='parked'
        )
        
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator,
            matched_user=self.user,
            matched_plate=self.plate,
            session=session
        )
        
        self.assertEqual(gate_event.session, session)
        self.assertIn(gate_event, session.gate_events.all())


class ParkingSessionModelTest(TestCase):
    """
    Test suite for ParkingSession model.
    """
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            phone='+989123456789',
            password='testpass123',
            full_name='Test User',
            role='student'
        )
        self.plate = Plate.objects.create(
            user=self.user,
            plate_number='۱۲ب۳۴۵-۶۷',
            is_primary=True,
            is_active=True
        )
    
    def test_create_parking_session(self):
        """Test creating a parking session with required fields."""
        from django.utils import timezone
        session = ParkingSession.objects.create(
            plate=self.plate,
            entry_time=timezone.now(),
            status='parked'
        )
        
        self.assertIsNotNone(session.id)
        self.assertIsNotNone(session.created_at)
        self.assertEqual(session.status, 'parked')
    
    def test_parking_session_string_representation(self):
        """Test the string representation of parking session."""
        from django.utils import timezone
        session = ParkingSession.objects.create(
            plate=self.plate,
            entry_time=timezone.now(),
            status='parked'
        )
        
        str_repr = str(session)
        self.assertIn('Session', str_repr)
        self.assertIn(str(session.id), str_repr)



class ParkingSessionServiceTest(TestCase):
    """
    Test suite for ParkingSessionService.
    
    Tests session lifecycle: entry, exit, cash payment, fee waiver, and concurrent session handling.
    
    Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7,
                 19.1, 19.2, 19.3, 19.4, 19.5, 19.6, 20.1, 20.2, 20.3, 20.4, 20.5,
                 80.1, 80.2, 80.3, 80.4, 80.5
    """
    
    def setUp(self):
        """Set up test data."""
        from wallets.models import Wallet
        from .services import ParkingSessionService
        
        self.service = ParkingSessionService
        
        # Create test users
        self.student = User.objects.create_user(
            phone='+989123456789',
            password='testpass123',
            full_name='Test Student',
            student_id='40012345',
            role='student'
        )
        
        self.operator = User.objects.create_user(
            phone='+989123456790',
            password='testpass123',
            full_name='Test Operator',
            role='operator'
        )
        
        # Create test plate
        self.plate = Plate.objects.create(
            user=self.student,
            plate_number='۱۲ب۳۴۵-۶۷',
            is_primary=True,
            is_active=True
        )
        
        # Top up student wallet
        self.wallet = Wallet.objects.get(user=self.student)
        self.wallet.balance = Decimal('100000')
        self.wallet.save()
    
    def test_create_entry_session_registered_plate(self):
        """
        Test creating entry session for registered plate.
        
        Requirements: 15.1, 15.2, 15.3, 15.5, 15.6, 15.7
        """
        # Create entry gate event
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_raw='۱۲ب۳۴۵-۶۷',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            confidence_score=Decimal('0.9500'),
            operator=self.operator,
            matched_user=self.student,
            matched_plate=self.plate
        )
        
        # Create entry session
        session = self.service.create_entry_session(gate_event)
        
        # Verify session was created correctly
        self.assertIsNotNone(session.id)
        self.assertEqual(session.plate, self.plate)
        self.assertIsNone(session.guest_plate_number)
        self.assertEqual(session.entry_event, gate_event)
        self.assertEqual(session.entry_time, gate_event.created_at)
        self.assertEqual(session.status, 'parked')
        self.assertIsNone(session.exit_event)
        self.assertIsNone(session.exit_time)
        
        # Verify gate event was linked to session
        gate_event.refresh_from_db()
        self.assertEqual(gate_event.session, session)
    
    def test_create_entry_session_guest_plate(self):
        """
        Test creating entry session for guest (unregistered) plate.
        
        Requirements: 15.1, 15.2, 15.4, 15.5, 15.6, 15.7
        """
        # Create entry gate event without matched plate
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_raw='۸۸د۹۹۹-۱۱',
            plate_confirmed='۸۸د۹۹۹-۱۱',
            confidence_score=Decimal('0.9200'),
            operator=self.operator
        )
        
        # Create entry session
        session = self.service.create_entry_session(gate_event)
        
        # Verify session was created for guest
        self.assertIsNotNone(session.id)
        self.assertIsNone(session.plate)
        self.assertEqual(session.guest_plate_number, '۸۸د۹۹۹-۱۱')
        self.assertEqual(session.status, 'parked')
    
    def test_create_entry_session_invalid_direction(self):
        """
        Test that creating entry session with exit gate event raises error.
        """
        # Create exit gate event
        gate_event = GateEvent.objects.create(
            camera_id='exit',
            direction='exit',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator
        )
        
        # Attempt to create entry session should raise error
        with self.assertRaises(ValidationError) as context:
            self.service.create_entry_session(gate_event)
        
        self.assertIn('entry', str(context.exception).lower())
    
    def test_concurrent_session_prevention(self):
        """
        Test that creating new entry session auto-closes existing parked session.
        
        Requirements: 80.1, 80.2
        """
        # Create first entry
        gate_event1 = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator,
            matched_plate=self.plate
        )
        session1 = self.service.create_entry_session(gate_event1)
        
        # Verify first session is parked
        self.assertEqual(session1.status, 'parked')
        
        # Create second entry without exit (concurrent session)
        gate_event2 = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator,
            matched_plate=self.plate
        )
        session2 = self.service.create_entry_session(gate_event2)
        
        # Verify second session is parked
        self.assertEqual(session2.status, 'parked')
        
        # Verify first session was auto-closed (flagged)
        session1.refresh_from_db()
        self.assertEqual(session1.status, 'flagged')
        self.assertIn('Auto-closed', session1.notes)
    
    def test_close_exit_session_with_wallet_payment(self):
        """
        Test closing exit session with successful wallet payment.
        
        Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7,
                     18.1, 18.2, 18.3, 18.4, 18.7
        """
        from datetime import timedelta
        from django.utils import timezone
        from unittest.mock import patch
        
        # Create entry session
        entry_time = timezone.now()
        with patch('django.utils.timezone.now', return_value=entry_time):
            entry_event = GateEvent.objects.create(
                camera_id='entry',
                direction='entry',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate,
                matched_user=self.student
            )
            session = self.service.create_entry_session(entry_event)
        
        # Simulate 2 hours parking
        exit_time = entry_time + timedelta(hours=2)
        
        # Create exit gate event
        with patch('django.utils.timezone.now', return_value=exit_time):
            exit_event = GateEvent.objects.create(
                camera_id='exit',
                direction='exit',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate,
                matched_user=self.student
            )
        
        # Close exit session
        result = self.service.close_exit_session(exit_event)
        
        # Verify result
        self.assertIsNotNone(result['session'])
        self.assertEqual(result['payment_status'], 'completed')
        self.assertTrue(result['wallet_sufficient'])
        
        # 120 min - 10 grace = 110 billable → 110*5000//60 = 9166, student 80% → 7332
        expected_fee = 7332
        self.assertEqual(result['fee'], expected_fee)
        
        # Verify session was updated
        session.refresh_from_db()
        self.assertEqual(session.exit_event, exit_event)
        self.assertEqual(session.exit_time, exit_time)
        self.assertEqual(session.duration_minutes, 120)
        self.assertEqual(session.fee_charged, Decimal(expected_fee))
        self.assertEqual(session.status, 'completed')
        self.assertEqual(session.payment_method, 'wallet')
        
        # Verify wallet was debited
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('100000') - Decimal(expected_fee))
        
        # Verify gate event was linked
        exit_event.refresh_from_db()
        self.assertEqual(exit_event.session, session)
    
    def test_close_exit_session_insufficient_balance(self):
        """
        Test closing exit session with insufficient wallet balance.
        
        Requirements: 17.5, 18.5, 18.6
        """
        from datetime import timedelta
        from django.utils import timezone
        from unittest.mock import patch
        
        # Set low wallet balance
        self.wallet.balance = Decimal('1000')
        self.wallet.save()
        
        # Create entry session
        entry_time = timezone.now()
        with patch('django.utils.timezone.now', return_value=entry_time):
            entry_event = GateEvent.objects.create(
                camera_id='entry',
                direction='entry',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate,
                matched_user=self.student
            )
            session = self.service.create_entry_session(entry_event)
        
        # Simulate 2 hours parking (fee will be 7332 for student)
        exit_time = entry_time + timedelta(hours=2)
        
        # Create exit gate event
        with patch('django.utils.timezone.now', return_value=exit_time):
            exit_event = GateEvent.objects.create(
                camera_id='exit',
                direction='exit',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate,
                matched_user=self.student
            )
        
        # Close exit session
        result = self.service.close_exit_session(exit_event)
        
        # Verify result
        self.assertEqual(result['payment_status'], 'unpaid')
        self.assertFalse(result['wallet_sufficient'])
        
        # Verify session status is unpaid
        session.refresh_from_db()
        self.assertEqual(session.status, 'unpaid')
        self.assertIsNone(session.payment_method)
        
        # Verify wallet was NOT debited
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('1000'))
    
    def test_close_exit_session_grace_period(self):
        """
        Test closing exit session within grace period (no fee).
        
        Requirements: 16.4, 17.4
        """
        from datetime import timedelta
        from django.utils import timezone
        from unittest.mock import patch
        
        # Create entry session
        entry_time = timezone.now()
        with patch('django.utils.timezone.now', return_value=entry_time):
            entry_event = GateEvent.objects.create(
                camera_id='entry',
                direction='entry',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate,
                matched_user=self.student
            )
            session = self.service.create_entry_session(entry_event)
        
        # Simulate 5 minutes parking (within grace period)
        exit_time = entry_time + timedelta(minutes=5)
        
        # Create exit gate event
        with patch('django.utils.timezone.now', return_value=exit_time):
            exit_event = GateEvent.objects.create(
                camera_id='exit',
                direction='exit',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate,
                matched_user=self.student
            )
        
        # Close exit session
        result = self.service.close_exit_session(exit_event)
        
        # Verify no fee charged
        self.assertEqual(result['fee'], 0)
        self.assertEqual(result['payment_status'], 'completed')
        
        # Verify session
        session.refresh_from_db()
        self.assertEqual(session.fee_charged, Decimal('0'))
        self.assertEqual(session.status, 'completed')
    
    def test_close_exit_session_guest_plate(self):
        """
        Test closing exit session for guest plate (unpaid).
        
        Requirements: 17.1, 17.5
        """
        from datetime import timedelta
        from django.utils import timezone
        from unittest.mock import patch
        
        # Create entry session for guest
        entry_time = timezone.now()
        with patch('django.utils.timezone.now', return_value=entry_time):
            entry_event = GateEvent.objects.create(
                camera_id='entry',
                direction='entry',
                plate_confirmed='۸۸د۹۹۹-۱۱',
                operator=self.operator
            )
            session = self.service.create_entry_session(entry_event)
        
        # Simulate 1 hour parking
        exit_time = entry_time + timedelta(hours=1)
        
        # Create exit gate event
        with patch('django.utils.timezone.now', return_value=exit_time):
            exit_event = GateEvent.objects.create(
                camera_id='exit',
                direction='exit',
                plate_confirmed='۸۸د۹۹۹-۱۱',
                operator=self.operator
            )
        
        # Close exit session
        result = self.service.close_exit_session(exit_event)
        
        # Verify guest session is unpaid
        self.assertEqual(result['payment_status'], 'unpaid')
        
        # 60 min - 10 grace = 50 billable → 50*5000//60 = 4166
        self.assertEqual(result['fee'], 4166)
        
        # Verify session
        session.refresh_from_db()
        self.assertEqual(session.status, 'unpaid')
        self.assertEqual(session.fee_charged, Decimal('4166'))

    def test_close_exit_finds_guest_session_for_registered_plate(self):
        """Legacy guest session should close and charge wallet on registered exit."""
        from datetime import timedelta
        from unittest.mock import patch

        entry_time = timezone.now()
        session = ParkingSession.objects.create(
            guest_plate_number='۱۲ب۳۴۵-۶۷',
            entry_time=entry_time,
            status='parked',
        )
        self.assertIsNone(session.plate_id)

        exit_time = entry_time + timedelta(hours=2)
        with patch('django.utils.timezone.now', return_value=exit_time):
            exit_event = GateEvent.objects.create(
                camera_id='exit',
                direction='exit',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate,
                matched_user=self.student,
            )
            result = self.service.close_exit_session(exit_event)

        self.assertEqual(result['payment_status'], 'completed')
        self.assertEqual(result['fee'], 7332)
        session.refresh_from_db()
        self.assertEqual(session.plate_id, self.plate.id)
        self.assertIsNone(session.guest_plate_number)
        self.assertEqual(session.status, 'completed')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('100000') - Decimal('7332'))

    def test_parked_list_resolves_registered_plate(self):
        """Parked API should not list registered users as guests."""
        from rest_framework.test import APIClient

        ParkingSession.objects.create(
            guest_plate_number='۱۲ب۳۴۵-۶۷',
            entry_time=timezone.now(),
            status='parked',
        )
        client = APIClient()
        client.force_authenticate(user=self.operator)
        response = client.get('/api/parking/sessions/?status=parked')
        self.assertEqual(response.status_code, 200)
        row = response.data['results'][0]
        self.assertTrue(row['is_registered'])
        self.assertEqual(row['user_name'], self.student.full_name)
        self.assertIsNotNone(row['wallet_balance'])
    
    def test_close_exit_session_no_active_session(self):
        """
        Test closing exit session when no active session exists.
        
        Requirements: 17.1
        """
        # Create exit gate event without prior entry
        exit_event = GateEvent.objects.create(
            camera_id='exit',
            direction='exit',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator,
            matched_plate=self.plate
        )
        
        # Close exit session
        result = self.service.close_exit_session(exit_event)
        
        # Verify no session found
        self.assertIsNone(result['session'])
        self.assertEqual(result['payment_status'], 'no_session')
        self.assertEqual(result['fee'], 0)
    
    def test_close_exit_session_invalid_direction(self):
        """
        Test that closing exit session with entry gate event raises error.
        """
        # Create entry gate event
        gate_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator
        )
        
        # Attempt to close exit session should raise error
        with self.assertRaises(ValidationError) as context:
            self.service.close_exit_session(gate_event)
        
        self.assertIn('exit', str(context.exception).lower())
    
    def test_record_cash_payment(self):
        """
        Test recording cash payment for unpaid session.
        
        Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6
        """
        from datetime import timedelta
        from django.utils import timezone
        from unittest.mock import patch
        
        # Create unpaid session
        entry_time = timezone.now()
        with patch('django.utils.timezone.now', return_value=entry_time):
            entry_event = GateEvent.objects.create(
                camera_id='entry',
                direction='entry',
                plate_confirmed='۸۸د۹۹۹-۱۱',
                operator=self.operator
            )
            session = self.service.create_entry_session(entry_event)
        
        exit_time = entry_time + timedelta(hours=1)
        with patch('django.utils.timezone.now', return_value=exit_time):
            exit_event = GateEvent.objects.create(
                camera_id='exit',
                direction='exit',
                plate_confirmed='۸۸د۹۹۹-۱۱',
                operator=self.operator
            )
        self.service.close_exit_session(exit_event)
        
        # Verify session is unpaid
        session.refresh_from_db()
        self.assertEqual(session.status, 'unpaid')
        
        # Record cash payment
        notes = "Paid 5000 Toman in cash"
        updated_session = self.service.record_cash_payment(
            session_id=session.id,
            operator_id=self.operator.id,
            notes=notes
        )
        
        # Verify session was updated
        self.assertEqual(updated_session.status, 'completed')
        self.assertEqual(updated_session.payment_method, 'cash')
        self.assertEqual(updated_session.collected_by, self.operator)
        self.assertIn(notes, updated_session.notes)
    
    def test_record_cash_payment_invalid_status(self):
        """
        Test that recording cash payment for non-unpaid session raises error.
        
        Requirements: 19.5
        """
        from datetime import timedelta
        from django.utils import timezone
        from unittest.mock import patch
        
        # Create completed session
        entry_time = timezone.now()
        with patch('django.utils.timezone.now', return_value=entry_time):
            entry_event = GateEvent.objects.create(
                camera_id='entry',
                direction='entry',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate,
                matched_user=self.student
            )
            session = self.service.create_entry_session(entry_event)
        
        exit_time = entry_time + timedelta(minutes=5)
        with patch('django.utils.timezone.now', return_value=exit_time):
            exit_event = GateEvent.objects.create(
                camera_id='exit',
                direction='exit',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate
            )
        self.service.close_exit_session(exit_event)
        
        # Verify session is completed
        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')
        
        # Attempt to record cash payment should raise error
        with self.assertRaises(ValidationError) as context:
            self.service.record_cash_payment(
                session_id=session.id,
                operator_id=self.operator.id
            )
        
        self.assertIn('unpaid', str(context.exception).lower())
    
    def test_waive_fee_parked_session(self):
        """
        Test waiving fee for parked session.
        
        Requirements: 20.1, 20.2, 20.3, 20.4, 20.5
        """
        # Create parked session
        entry_event = GateEvent.objects.create(
            camera_id='entry',
            direction='entry',
            plate_confirmed='۱۲ب۳۴۵-۶۷',
            operator=self.operator,
            matched_plate=self.plate
        )
        session = self.service.create_entry_session(entry_event)
        
        # Verify session is parked
        self.assertEqual(session.status, 'parked')
        
        # Waive fee
        updated_session = self.service.waive_fee(
            session_id=session.id,
            operator_id=self.operator.id
        )
        
        # Verify session was updated
        self.assertEqual(updated_session.fee_charged, Decimal('0'))
        self.assertEqual(updated_session.status, 'waived')
        self.assertEqual(updated_session.payment_method, 'waived')
        self.assertEqual(updated_session.collected_by, self.operator)
    
    def test_waive_fee_unpaid_session(self):
        """
        Test waiving fee for unpaid session.
        
        Requirements: 20.1, 20.2, 20.3, 20.4, 20.5
        """
        from datetime import timedelta
        from django.utils import timezone
        from unittest.mock import patch
        
        # Create unpaid session
        entry_time = timezone.now()
        with patch('django.utils.timezone.now', return_value=entry_time):
            entry_event = GateEvent.objects.create(
                camera_id='entry',
                direction='entry',
                plate_confirmed='۸۸د۹۹۹-۱۱',
                operator=self.operator
            )
            session = self.service.create_entry_session(entry_event)
        
        exit_time = entry_time + timedelta(hours=1)
        with patch('django.utils.timezone.now', return_value=exit_time):
            exit_event = GateEvent.objects.create(
                camera_id='exit',
                direction='exit',
                plate_confirmed='۸۸د۹۹۹-۱۱',
                operator=self.operator
            )
        self.service.close_exit_session(exit_event)
        
        # Verify session is unpaid
        session.refresh_from_db()
        self.assertEqual(session.status, 'unpaid')
        
        # Waive fee
        updated_session = self.service.waive_fee(
            session_id=session.id,
            operator_id=self.operator.id
        )
        
        # Verify session was updated
        self.assertEqual(updated_session.fee_charged, Decimal('0'))
        self.assertEqual(updated_session.status, 'waived')
        self.assertEqual(updated_session.payment_method, 'waived')
    
    def test_waive_fee_invalid_status(self):
        """
        Test that waiving fee for completed session raises error.
        
        Requirements: 20.5
        """
        from datetime import timedelta
        from django.utils import timezone
        from unittest.mock import patch
        
        # Create completed session
        entry_time = timezone.now()
        with patch('django.utils.timezone.now', return_value=entry_time):
            entry_event = GateEvent.objects.create(
                camera_id='entry',
                direction='entry',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate,
                matched_user=self.student
            )
            session = self.service.create_entry_session(entry_event)
        
        exit_time = entry_time + timedelta(minutes=5)
        with patch('django.utils.timezone.now', return_value=exit_time):
            exit_event = GateEvent.objects.create(
                camera_id='exit',
                direction='exit',
                plate_confirmed='۱۲ب۳۴۵-۶۷',
                operator=self.operator,
                matched_plate=self.plate
            )
        self.service.close_exit_session(exit_event)
        
        # Verify session is completed
        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')
        
        # Attempt to waive fee should raise error
        with self.assertRaises(ValidationError) as context:
            self.service.waive_fee(
                session_id=session.id,
                operator_id=self.operator.id
            )
        
        self.assertIn('parked', str(context.exception).lower())
        self.assertIn('unpaid', str(context.exception).lower())



# ============================================================================
# Integration Tests for Gate Event Confirmation Handler (Task 7.3)
# ============================================================================

import asyncio
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import AccessToken


class GateEventConfirmHandlerTest(TransactionTestCase):
    """
    Integration tests for the gate event confirmation handler.

    Tests the handle_gate_event_confirm flow end-to-end via the WebSocket
    consumer using Django Channels' WebsocketCommunicator.

    Requirements: 13.1, 13.2, 14.1, 14.2, 14.3, 14.4, 14.5, 15.1, 17.1,
                 24.3, 24.4, 24.5, 24.6
    """

    def setUp(self):
        """Set up test data: operator user, student user, plate, and wallet."""
        from wallets.models import Wallet

        # Create operator user
        self.operator = User.objects.create_user(
            phone='+989200000001',
            password='testpass123',
            full_name='Test Operator',
            role='operator'
        )

        # Create student user with sufficient wallet balance
        self.student = User.objects.create_user(
            phone='+989200000002',
            password='testpass123',
            full_name='Test Student',
            student_id='40099999',
            role='student'
        )

        # Create registered plate for student
        self.plate = Plate.objects.create(
            user=self.student,
            plate_number='۱۲ب۳۴۵-۶۷',
            is_primary=True,
            is_active=True
        )

        # Top up student wallet to 100,000 Toman
        self.wallet = Wallet.objects.get(user=self.student)
        self.wallet.balance = Decimal('100000')
        self.wallet.save()

        # Generate JWT token for operator
        self.token = str(AccessToken.for_user(self.operator))

    def _get_application(self):
        """Return the ASGI application for testing."""
        from config.asgi import application
        return application

    def _run(self, coro):
        """Run an async coroutine synchronously."""
        return asyncio.get_event_loop().run_until_complete(coro)

    async def _connect(self, token=None):
        """Helper to create and connect a WebsocketCommunicator."""
        t = token or self.token
        communicator = WebsocketCommunicator(
            self._get_application(),
            f'/ws/panel/?token={t}'
        )
        connected, subprotocol = await communicator.connect()
        return communicator, connected

    def test_gate_event_confirm_entry_creates_session(self):
        """
        Send a gate_event.confirm with direction='entry', verify gate_event.ack
        is received with correct event_id, session_id, payment_status='parked'.

        Requirements: 13.1, 13.2, 15.1, 24.3, 24.4
        """
        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected, "WebSocket connection should succeed")

            try:
                # Send gate_event.confirm for entry
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۱۲ب۳۴۵-۶۷',
                    'plate_confirmed': '۱۲ب۳۴۵-۶۷',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False
                })

                # Receive ack
                response = await communicator.receive_json_from(timeout=5)

                self.assertEqual(response['type'], 'gate_event.ack')
                self.assertIsNotNone(response['event_id'])
                self.assertIsNotNone(response['session_id'])
                self.assertEqual(response['payment_status'], 'parked')
                self.assertIn('wallet_sufficient', response)
                self.assertIsNone(response['wallet_sufficient'])  # Not applicable for entry

                # Verify GateEvent was created in DB (using sync_to_async)
                @database_sync_to_async
                def check_gate_event():
                    gate_event = GateEvent.objects.get(id=response['event_id'])
                    self.assertEqual(gate_event.direction, 'entry')
                    self.assertEqual(gate_event.plate_confirmed, '۱۲ب۳۴۵-۶۷')

                await check_gate_event()

                # Verify ParkingSession was created
                @database_sync_to_async
                def check_session():
                    session = ParkingSession.objects.get(id=response['session_id'])
                    self.assertEqual(session.status, 'parked')

                await check_session()

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_gate_event_confirm_exit_closes_session_wallet_payment(self):
        """
        Send entry then exit confirm for a registered user with sufficient balance.
        Verify ack has payment_status='completed', wallet_sufficient=True, correct fee.

        Requirements: 17.1, 24.4, 24.5
        """
        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected)

            try:
                # Step 1: Entry
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۱۲ب۳۴۵-۶۷',
                    'plate_confirmed': '۱۲ب۳۴۵-۶۷',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False
                })
                entry_ack = await communicator.receive_json_from(timeout=5)
                self.assertEqual(entry_ack['type'], 'gate_event.ack')
                self.assertEqual(entry_ack['payment_status'], 'parked')

                # Consume the stats.update broadcast after entry (task 7.4)
                entry_stats = await communicator.receive_json_from(timeout=5)
                self.assertEqual(entry_stats['type'], 'stats.update')

                # Manually set entry_time to 2 hours ago so fee is non-zero
                from django.utils import timezone
                from datetime import timedelta
                two_hours_ago = timezone.now() - timedelta(hours=2)

                @database_sync_to_async
                def backdate_session():
                    ParkingSession.objects.filter(id=entry_ack['session_id']).update(
                        entry_time=two_hours_ago
                    )
                    GateEvent.objects.filter(id=entry_ack['event_id']).update(
                        created_at=two_hours_ago
                    )

                await backdate_session()

                # Step 2: Exit
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'exit',
                    'direction': 'exit',
                    'plate_raw': '۱۲ب۳۴۵-۶۷',
                    'plate_confirmed': '۱۲ب۳۴۵-۶۷',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False
                })
                exit_ack = await communicator.receive_json_from(timeout=5)

                self.assertEqual(exit_ack['type'], 'gate_event.ack')
                self.assertEqual(exit_ack['payment_status'], 'completed')
                self.assertTrue(exit_ack['wallet_sufficient'])
                # Proportional fee for 2h with student discount
                self.assertEqual(exit_ack['fee'], 7332)
                self.assertIsNotNone(exit_ack['session_id'])

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_gate_event_confirm_exit_insufficient_balance(self):
        """
        Send entry then exit confirm with low wallet balance.
        Verify ack has payment_status='unpaid', wallet_sufficient=False.

        Requirements: 17.1, 24.5
        """
        # Set wallet balance to very low amount (synchronous, in setUp context)
        self.wallet.balance = Decimal('100')
        self.wallet.save()

        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected)

            try:
                # Step 1: Entry
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۱۲ب۳۴۵-۶۷',
                    'plate_confirmed': '۱۲ب۳۴۵-۶۷',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False
                })
                entry_ack = await communicator.receive_json_from(timeout=5)
                self.assertEqual(entry_ack['type'], 'gate_event.ack')

                # Consume the stats.update broadcast after entry (task 7.4)
                entry_stats = await communicator.receive_json_from(timeout=5)
                self.assertEqual(entry_stats['type'], 'stats.update')

                # Manually set entry_time to 2 hours ago so fee is non-zero
                from django.utils import timezone
                from datetime import timedelta
                two_hours_ago = timezone.now() - timedelta(hours=2)

                @database_sync_to_async
                def backdate_session():
                    ParkingSession.objects.filter(id=entry_ack['session_id']).update(
                        entry_time=two_hours_ago
                    )
                    GateEvent.objects.filter(id=entry_ack['event_id']).update(
                        created_at=two_hours_ago
                    )

                await backdate_session()

                # Step 2: Exit
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'exit',
                    'direction': 'exit',
                    'plate_raw': '۱۲ب۳۴۵-۶۷',
                    'plate_confirmed': '۱۲ب۳۴۵-۶۷',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False
                })
                exit_ack = await communicator.receive_json_from(timeout=5)

                self.assertEqual(exit_ack['type'], 'gate_event.ack')
                self.assertEqual(exit_ack['payment_status'], 'unpaid')
                self.assertFalse(exit_ack['wallet_sufficient'])

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_gate_event_confirm_unregistered_plate(self):
        """
        Send confirm for an unregistered plate.
        Verify matched_user=None in ack.

        Requirements: 13.2, 24.4
        """
        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected)

            try:
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۹۹ج۱۲۳-۴۵',
                    'plate_confirmed': '۹۹ج۱۲۳-۴۵',
                    'confidence_score': 0.88,
                    'was_edited': False,
                    'was_auto_approved': False
                })

                response = await communicator.receive_json_from(timeout=5)

                self.assertEqual(response['type'], 'gate_event.ack')
                self.assertIsNone(response['matched_user'])
                self.assertIsNotNone(response['session_id'])
                self.assertEqual(response['payment_status'], 'parked')

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_gate_event_confirm_missing_fields(self):
        """
        Send confirm without required fields.
        Verify error response is returned.

        Requirements: 75.2, 75.3
        """
        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected)

            try:
                # Send message missing 'plate_confirmed' and 'direction'
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'plate_raw': '۱۲ب۳۴۵-۶۷'
                    # Missing: direction, plate_confirmed
                })

                response = await communicator.receive_json_from(timeout=5)

                self.assertEqual(response['type'], 'error')
                self.assertIn('Missing required fields', response['message'])

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_gate_event_confirm_invalid_token_rejected(self):
        """
        Verify that a connection with an invalid JWT token is rejected.

        Requirements: 21.2, 21.4
        """
        async def run():
            communicator, connected = await self._connect(token='invalid.token.here')
            self.assertFalse(connected, "Connection with invalid token should be rejected")
            await communicator.disconnect()

        self._run(run())


# ============================================================================
# Integration Tests for Statistics Broadcasting (Task 7.4)
# ============================================================================


class StatsBroadcastTest(TransactionTestCase):
    """
    Integration tests for the broadcast_stats() method and stats.update message.

    Tests that:
    - stats.update is broadcast after gate_event.confirm (entry/exit)
    - stats.update is broadcast after session.cash_payment
    - stats.update is broadcast after session.waive_fee
    - stats.update message contains all required fields
    - Statistics are calculated correctly using Asia/Tehran timezone

    Requirements: 25.1, 25.2, 25.3, 25.4, 25.5, 53.4, 65.1, 65.2, 65.3
    """

    def setUp(self):
        """Set up test data: operator user, student user, plate, and wallet."""
        from wallets.models import Wallet

        # Create operator user
        self.operator = User.objects.create_user(
            phone='+989300000001',
            password='testpass123',
            full_name='Stats Test Operator',
            role='operator'
        )

        # Create student user
        self.student = User.objects.create_user(
            phone='+989300000002',
            password='testpass123',
            full_name='Stats Test Student',
            student_id='40088888',
            role='student'
        )

        # Create registered plate for student
        self.plate = Plate.objects.create(
            user=self.student,
            plate_number='۱۱ب۲۲۲-۳۳',
            is_primary=True,
            is_active=True
        )

        # Top up student wallet to 100,000 Toman
        self.wallet = Wallet.objects.get(user=self.student)
        self.wallet.balance = Decimal('100000')
        self.wallet.save()

        # Generate JWT token for operator
        self.token = str(AccessToken.for_user(self.operator))

    def _get_application(self):
        """Return the ASGI application for testing."""
        from config.asgi import application
        return application

    def _run(self, coro):
        """Run an async coroutine synchronously."""
        return asyncio.get_event_loop().run_until_complete(coro)

    async def _connect(self, token=None):
        """Helper to create and connect a WebsocketCommunicator."""
        t = token or self.token
        communicator = WebsocketCommunicator(
            self._get_application(),
            f'/ws/panel/?token={t}'
        )
        connected, subprotocol = await communicator.connect()
        return communicator, connected

    def test_stats_update_broadcast_after_entry(self):
        """
        After a gate_event.confirm (entry), a stats.update message should be
        broadcast to all connected operator panels.

        Requirements: 25.1, 25.2, 65.1
        """
        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected, "WebSocket connection should succeed")

            try:
                # Send gate_event.confirm for entry
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۱۱ب۲۲۲-۳۳',
                    'plate_confirmed': '۱۱ب۲۲۲-۳۳',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False
                })

                # First message: gate_event.ack
                ack = await communicator.receive_json_from(timeout=5)
                self.assertEqual(ack['type'], 'gate_event.ack')

                # Second message: stats.update broadcast
                stats_msg = await communicator.receive_json_from(timeout=5)
                self.assertEqual(stats_msg['type'], 'stats.update')

                # Verify all required fields are present (Requirement 25.2)
                data = stats_msg['data']
                self.assertIn('entries_today', data)
                self.assertIn('exits_today', data)
                self.assertIn('currently_parked', data)
                self.assertIn('revenue_today', data)
                self.assertIn('capacity', data)

                # After one entry, currently_parked should be >= 1
                self.assertGreaterEqual(data['currently_parked'], 1)
                # entries_today should be >= 1
                self.assertGreaterEqual(data['entries_today'], 1)
                # capacity should be a positive integer
                self.assertGreater(data['capacity'], 0)

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_stats_update_broadcast_after_exit(self):
        """
        After a gate_event.confirm (exit), a stats.update message should be
        broadcast with updated exits_today count.

        Requirements: 25.1, 25.2, 65.1
        """
        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected)

            try:
                # Step 1: Entry
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۱۱ب۲۲۲-۳۳',
                    'plate_confirmed': '۱۱ب۲۲۲-۳۳',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False
                })
                entry_ack = await communicator.receive_json_from(timeout=5)
                self.assertEqual(entry_ack['type'], 'gate_event.ack')

                # Consume the stats.update from entry
                entry_stats = await communicator.receive_json_from(timeout=5)
                self.assertEqual(entry_stats['type'], 'stats.update')

                # Step 2: Exit
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'exit',
                    'direction': 'exit',
                    'plate_raw': '۱۱ب۲۲۲-۳۳',
                    'plate_confirmed': '۱۱ب۲۲۲-۳۳',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False
                })
                exit_ack = await communicator.receive_json_from(timeout=5)
                self.assertEqual(exit_ack['type'], 'gate_event.ack')

                # Receive stats.update after exit
                exit_stats = await communicator.receive_json_from(timeout=5)
                self.assertEqual(exit_stats['type'], 'stats.update')

                data = exit_stats['data']
                # exits_today should be >= 1
                self.assertGreaterEqual(data['exits_today'], 1)
                # currently_parked should be 0 (session closed)
                self.assertEqual(data['currently_parked'], 0)

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_stats_update_broadcast_after_cash_payment(self):
        """
        After a session.cash_payment, a stats.update message should be broadcast.

        Requirements: 25.1, 65.2
        """
        # Create an unpaid session directly in the DB
        from django.utils import timezone as tz
        from datetime import timedelta

        entry_time = tz.now() - timedelta(hours=2)
        session = ParkingSession.objects.create(
            plate=self.plate,
            entry_time=entry_time,
            status='unpaid',
            fee_charged=Decimal('8000')
        )

        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected)

            try:
                # Send cash payment
                await communicator.send_json_to({
                    'type': 'session.cash_payment',
                    'session_id': session.id,
                    'notes': 'Test cash payment'
                })

                # First message: cash_payment_ack
                ack = await communicator.receive_json_from(timeout=5)
                self.assertEqual(ack['type'], 'session.cash_payment_ack')
                self.assertEqual(ack['status'], 'completed')

                # Second message: stats.update broadcast (Requirement 65.2)
                stats_msg = await communicator.receive_json_from(timeout=5)
                self.assertEqual(stats_msg['type'], 'stats.update')

                data = stats_msg['data']
                self.assertIn('entries_today', data)
                self.assertIn('exits_today', data)
                self.assertIn('currently_parked', data)
                self.assertIn('revenue_today', data)
                self.assertIn('capacity', data)

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_stats_update_broadcast_after_waive_fee(self):
        """
        After a session.waive_fee, a stats.update message should be broadcast.

        Requirements: 25.1, 65.3
        """
        from django.utils import timezone as tz
        from datetime import timedelta

        entry_time = tz.now() - timedelta(hours=1)
        session = ParkingSession.objects.create(
            plate=self.plate,
            entry_time=entry_time,
            status='unpaid',
            fee_charged=Decimal('5000')
        )

        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected)

            try:
                # Send waive_fee
                await communicator.send_json_to({
                    'type': 'session.waive_fee',
                    'session_id': session.id
                })

                # First message: waive_fee_ack
                ack = await communicator.receive_json_from(timeout=5)
                self.assertEqual(ack['type'], 'session.waive_fee_ack')
                self.assertEqual(ack['status'], 'waived')
                self.assertEqual(ack['fee_charged'], 0)

                # Second message: stats.update broadcast (Requirement 65.3)
                stats_msg = await communicator.receive_json_from(timeout=5)
                self.assertEqual(stats_msg['type'], 'stats.update')

                data = stats_msg['data']
                self.assertIn('entries_today', data)
                self.assertIn('exits_today', data)
                self.assertIn('currently_parked', data)
                self.assertIn('revenue_today', data)
                self.assertIn('capacity', data)

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_stats_revenue_counts_only_completed_and_waived(self):
        """
        Revenue today should only count sessions with status='completed' or 'waived'.
        Sessions with status='unpaid' or 'parked' should not be counted.

        Requirements: 25.5
        """
        from django.utils import timezone as tz
        from datetime import timedelta

        now = tz.now()
        entry_time = now - timedelta(hours=2)

        # Create a completed session with fee
        ParkingSession.objects.create(
            plate=self.plate,
            entry_time=entry_time,
            exit_time=now,
            status='completed',
            payment_method='cash',
            fee_charged=Decimal('10000')
        )

        # Create a waived session with fee=0
        ParkingSession.objects.create(
            plate=self.plate,
            entry_time=entry_time,
            exit_time=now,
            status='waived',
            payment_method='waived',
            fee_charged=Decimal('0')
        )

        # Create an unpaid session (should NOT be counted in revenue)
        ParkingSession.objects.create(
            plate=self.plate,
            entry_time=entry_time,
            status='unpaid',
            fee_charged=Decimal('5000')
        )

        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected)

            try:
                # Trigger a stats broadcast by sending a ping (won't broadcast stats)
                # Instead, directly call get_stats via a gate event confirm on a new plate
                # We'll use a guest plate to avoid conflicts
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۵۵ک۶۶۶-۷۷',
                    'plate_confirmed': '۵۵ک۶۶۶-۷۷',
                    'confidence_score': 0.90,
                    'was_edited': False,
                    'was_auto_approved': False
                })

                # Consume gate_event.ack
                ack = await communicator.receive_json_from(timeout=5)
                self.assertEqual(ack['type'], 'gate_event.ack')

                # Receive stats.update
                stats_msg = await communicator.receive_json_from(timeout=5)
                self.assertEqual(stats_msg['type'], 'stats.update')

                data = stats_msg['data']
                # Revenue should be 10000 (completed) + 0 (waived) = 10000
                # The unpaid session (5000) should NOT be counted
                self.assertEqual(data['revenue_today'], 10000)

            finally:
                await communicator.disconnect()

        self._run(run())

    def test_stats_message_format(self):
        """
        Verify the stats.update message has the correct format:
        {"type": "stats.update", "data": {"entries_today": N, "exits_today": N,
         "currently_parked": N, "revenue_today": N, "capacity": N}}

        Requirements: 25.2
        """
        async def run():
            communicator, connected = await self._connect()
            self.assertTrue(connected)

            try:
                # Trigger stats broadcast via entry confirm
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۷۷م۸۸۸-۹۹',
                    'plate_confirmed': '۷۷م۸۸۸-۹۹',
                    'confidence_score': 0.90,
                    'was_edited': False,
                    'was_auto_approved': False
                })

                # Consume gate_event.ack
                ack = await communicator.receive_json_from(timeout=5)
                self.assertEqual(ack['type'], 'gate_event.ack')

                # Receive stats.update
                stats_msg = await communicator.receive_json_from(timeout=5)

                # Verify top-level structure
                self.assertEqual(stats_msg['type'], 'stats.update')
                self.assertIn('data', stats_msg)

                data = stats_msg['data']

                # Verify all required fields exist and are integers (Requirement 25.2)
                for field in ['entries_today', 'exits_today', 'currently_parked',
                              'revenue_today', 'capacity']:
                    self.assertIn(field, data, f"Missing field: {field}")
                    self.assertIsInstance(data[field], int,
                                         f"Field {field} should be an integer")

                # All counts should be non-negative
                self.assertGreaterEqual(data['entries_today'], 0)
                self.assertGreaterEqual(data['exits_today'], 0)
                self.assertGreaterEqual(data['currently_parked'], 0)
                self.assertGreaterEqual(data['revenue_today'], 0)
                self.assertGreater(data['capacity'], 0)

            finally:
                await communicator.disconnect()

        self._run(run())


# ============================================================================
# Integration Tests for ParkingConsumer WebSocket Consumer (Task 7.5)
# ============================================================================


class ParkingConsumerIntegrationTest(TransactionTestCase):
    """
    Integration tests for the ParkingConsumer WebSocket consumer.

    Tests connection authentication, gate event handling, stats broadcasting,
    and heartbeat ping/pong via Django Channels' WebsocketCommunicator.

    Requirements: 21.2, 21.3, 21.4, 23.2, 25.1
    """

    def setUp(self):
        """Set up test data: operator users, student user, plate, and wallet."""
        from wallets.models import Wallet

        # Create primary operator user
        self.operator = User.objects.create_user(
            phone='+989400000001',
            password='testpass123',
            full_name='Integration Test Operator',
            role='operator'
        )

        # Create second operator user (for broadcast tests)
        self.operator2 = User.objects.create_user(
            phone='+989400000002',
            password='testpass123',
            full_name='Integration Test Operator 2',
            role='operator'
        )

        # Create student user
        self.student = User.objects.create_user(
            phone='+989400000003',
            password='testpass123',
            full_name='Integration Test Student',
            student_id='40077777',
            role='student'
        )

        # Create registered plate for student
        self.plate = Plate.objects.create(
            user=self.student,
            plate_number='۱۲ب۳۴۵-۶۷',
            is_primary=True,
            is_active=True
        )

        # Top up student wallet to 100,000 Toman
        self.wallet = Wallet.objects.get(user=self.student)
        self.wallet.balance = Decimal('100000')
        self.wallet.save()

        # Generate JWT tokens
        self.token = str(AccessToken.for_user(self.operator))
        self.token2 = str(AccessToken.for_user(self.operator2))
        self.student_token = str(AccessToken.for_user(self.student))

    def _get_application(self):
        """Return the ASGI application for testing."""
        from config.asgi import application
        return application

    def _run(self, coro):
        """Run an async coroutine synchronously."""
        return asyncio.get_event_loop().run_until_complete(coro)

    async def _connect(self, token=None):
        """Helper to create and connect a WebsocketCommunicator."""
        t = token or self.token
        communicator = WebsocketCommunicator(
            self._get_application(),
            f'/ws/panel/?token={t}'
        )
        connected, subprotocol = await communicator.connect()
        return communicator, connected

    # ------------------------------------------------------------------
    # Test 1: Connection with valid JWT (Requirement 21.2, 21.3)
    # ------------------------------------------------------------------

    def test_connection_with_valid_jwt(self):
        """
        Test that a valid operator JWT allows WebSocket connection.

        Requirements: 21.2, 21.3
        """
        async def _test():
            communicator = WebsocketCommunicator(
                self._get_application(),
                f'/ws/panel/?token={self.token}'
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected, "Connection with valid operator JWT should succeed")
            await communicator.disconnect()

        self._run(_test())

    # ------------------------------------------------------------------
    # Test 2: Connection rejection with no token (Requirement 21.4)
    # ------------------------------------------------------------------

    def test_connection_rejection_no_token(self):
        """
        Test that a connection without a token is rejected.

        Requirements: 21.4
        """
        async def _test():
            communicator = WebsocketCommunicator(
                self._get_application(),
                '/ws/panel/'
            )
            connected, _ = await communicator.connect()
            self.assertFalse(connected, "Connection without token should be rejected")

        self._run(_test())

    # ------------------------------------------------------------------
    # Test 3: Connection rejection with invalid JWT (Requirement 21.4)
    # ------------------------------------------------------------------

    def test_connection_rejection_invalid_jwt(self):
        """
        Test that a connection with an invalid JWT token is rejected.

        Requirements: 21.4
        """
        async def _test():
            communicator = WebsocketCommunicator(
                self._get_application(),
                '/ws/panel/?token=invalid_token_xyz'
            )
            connected, _ = await communicator.connect()
            self.assertFalse(connected, "Connection with invalid JWT should be rejected")

        self._run(_test())

    # ------------------------------------------------------------------
    # Test 4: Connection rejection for student role (Requirement 21.4)
    # ------------------------------------------------------------------

    def test_connection_rejection_student_role(self):
        """
        Test that a student user cannot connect (only operators/admins allowed).

        Requirements: 21.4
        """
        async def _test():
            communicator = WebsocketCommunicator(
                self._get_application(),
                f'/ws/panel/?token={self.student_token}'
            )
            connected, _ = await communicator.connect()
            self.assertFalse(connected, "Connection with student JWT should be rejected")

        self._run(_test())

    # ------------------------------------------------------------------
    # Test 5: Heartbeat ping/pong (Requirement 23.2)
    # ------------------------------------------------------------------

    def test_ping_pong_heartbeat(self):
        """
        Test that sending a ping message receives a pong response.

        Requirements: 23.2
        """
        async def _test():
            communicator, connected = await self._connect()
            self.assertTrue(connected, "Connection should succeed")

            try:
                # Send ping
                await communicator.send_json_to({'type': 'ping'})

                # Receive pong
                response = await communicator.receive_json_from(timeout=5)
                self.assertEqual(response['type'], 'pong',
                                 "Response to ping should be pong")
            finally:
                await communicator.disconnect()

        self._run(_test())

    # ------------------------------------------------------------------
    # Test 6: gate_event.confirm creates session (Requirements 21.2, 21.3, 24.3)
    # ------------------------------------------------------------------

    def test_gate_event_confirm_creates_session(self):
        """
        Test that gate_event.confirm creates a GateEvent and ParkingSession in the DB.

        Requirements: 21.2, 21.3, 24.3
        """
        async def _test():
            communicator, connected = await self._connect()
            self.assertTrue(connected, "Connection should succeed")

            try:
                # Send gate_event.confirm for entry
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۱۲ب۳۴۵-۶۷',
                    'plate_confirmed': '۱۲ب۳۴۵-۶۷',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False,
                })

                # Receive gate_event.ack
                response = await communicator.receive_json_from(timeout=5)

                self.assertEqual(response['type'], 'gate_event.ack',
                                 "Response should be gate_event.ack")
                self.assertIn('event_id', response, "Response should contain event_id")
                self.assertIn('session_id', response, "Response should contain session_id")
                self.assertIsNotNone(response['event_id'], "event_id should not be None")
                self.assertIsNotNone(response['session_id'],
                                     "session_id should not be None (session was created)")

                event_id = response['event_id']
                session_id = response['session_id']

                # Verify GateEvent was created in DB
                @database_sync_to_async
                def check_gate_event():
                    event = GateEvent.objects.get(id=event_id)
                    self.assertEqual(event.direction, 'entry')
                    self.assertEqual(event.plate_confirmed, '۱۲ب۳۴۵-۶۷')
                    self.assertEqual(event.camera_id, 'entry')
                    self.assertFalse(event.was_rejected)

                await check_gate_event()

                # Verify ParkingSession was created with status='parked'
                @database_sync_to_async
                def check_session():
                    session = ParkingSession.objects.get(id=session_id)
                    self.assertEqual(session.status, 'parked',
                                     "Session should have status='parked'")

                await check_session()

            finally:
                await communicator.disconnect()

        self._run(_test())

    # ------------------------------------------------------------------
    # Test 7: stats.update broadcast after session change (Requirement 25.1)
    # ------------------------------------------------------------------

    def test_stats_update_broadcast_after_session_change(self):
        """
        Test that stats.update is broadcast to ALL connected operators after a session change.

        Two operators connect. Operator 1 sends gate_event.confirm. Both operators
        should receive the stats.update broadcast.

        Requirements: 25.1
        """
        async def _test():
            # Connect two communicators with different operator tokens
            comm1 = WebsocketCommunicator(
                self._get_application(),
                f'/ws/panel/?token={self.token}'
            )
            comm2 = WebsocketCommunicator(
                self._get_application(),
                f'/ws/panel/?token={self.token2}'
            )

            connected1, _ = await comm1.connect()
            connected2, _ = await comm2.connect()

            self.assertTrue(connected1, "Operator 1 connection should succeed")
            self.assertTrue(connected2, "Operator 2 connection should succeed")

            try:
                # Operator 1 sends gate_event.confirm (entry)
                await comm1.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    'direction': 'entry',
                    'plate_raw': '۱۲ب۳۴۵-۶۷',
                    'plate_confirmed': '۱۲ب۳۴۵-۶۷',
                    'confidence_score': 0.95,
                    'was_edited': False,
                    'was_auto_approved': False,
                })

                # Operator 1 receives gate_event.ack first
                ack = await comm1.receive_json_from(timeout=5)
                self.assertEqual(ack['type'], 'gate_event.ack',
                                 "Operator 1 should receive gate_event.ack")

                # Operator 1 receives stats.update
                stats1 = await comm1.receive_json_from(timeout=5)
                self.assertEqual(stats1['type'], 'stats.update',
                                 "Operator 1 should receive stats.update")

                # Operator 2 also receives stats.update (broadcast to all)
                stats2 = await comm2.receive_json_from(timeout=5)
                self.assertEqual(stats2['type'], 'stats.update',
                                 "Operator 2 should also receive stats.update broadcast")

                # Both stats messages should contain required fields
                for stats_msg in [stats1, stats2]:
                    data = stats_msg['data']
                    self.assertIn('entries_today', data)
                    self.assertIn('exits_today', data)
                    self.assertIn('currently_parked', data)
                    self.assertIn('revenue_today', data)
                    self.assertIn('capacity', data)

            finally:
                await comm1.disconnect()
                await comm2.disconnect()

        self._run(_test())

    # ------------------------------------------------------------------
    # Test 8: gate_event.confirm with missing fields returns error
    # ------------------------------------------------------------------

    def test_gate_event_confirm_missing_fields_returns_error(self):
        """
        Test that gate_event.confirm with missing required fields returns an error response.

        Requirements: 21.2
        """
        async def _test():
            communicator, connected = await self._connect()
            self.assertTrue(connected, "Connection should succeed")

            try:
                # Send gate_event.confirm with only camera_id (missing required fields)
                await communicator.send_json_to({
                    'type': 'gate_event.confirm',
                    'camera_id': 'entry',
                    # Missing: direction, plate_raw, plate_confirmed
                })

                # Receive error response
                response = await communicator.receive_json_from(timeout=5)

                self.assertEqual(response['type'], 'error',
                                 "Response should be an error")
                self.assertIn('missing', response['message'].lower(),
                              "Error message should mention 'missing'")

            finally:
                await communicator.disconnect()

        self._run(_test())

    # ------------------------------------------------------------------
    # Test 9: Message without type field returns error
    # ------------------------------------------------------------------

    def test_message_without_type_returns_error(self):
        """
        Test that a message without a 'type' field returns an error response.

        Requirements: 21.2
        """
        async def _test():
            communicator, connected = await self._connect()
            self.assertTrue(connected, "Connection should succeed")

            try:
                # Send message without 'type' field
                await communicator.send_json_to({'data': 'some_data'})

                # Receive error response
                response = await communicator.receive_json_from(timeout=5)

                self.assertEqual(response['type'], 'error',
                                 "Response should be an error when 'type' field is missing")

            finally:
                await communicator.disconnect()

        self._run(_test())


class CreateGateEventAPITest(TestCase):
    """HTTP API tests for POST /api/parking/gate-events/."""

    def setUp(self):
        from wallets.models import Wallet
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        self.client = APIClient()

        self.student = User.objects.create_user(
            phone='+989123456791',
            password='testpass123',
            full_name='API Test Student',
            student_id='40012346',
            role='student',
        )
        self.operator = User.objects.create_user(
            phone='+989123456792',
            password='testpass123',
            full_name='API Test Operator',
            role='operator',
        )
        self.plate = Plate.objects.create(
            user=self.student,
            plate_number='۱۲ب۳۴۵-۶۷',
            is_primary=True,
            is_active=True,
        )
        wallet = Wallet.objects.get(user=self.student)
        wallet.balance = Decimal('100000')
        wallet.save()

        refresh = RefreshToken.for_user(self.operator)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_create_entry_gate_event_via_http(self):
        response = self.client.post(
            '/api/parking/gate-events/',
            {
                'camera_id': 'entry',
                'direction': 'entry',
                'plate_raw': '۱۲ب۳۴۵-۶۷',
                'plate_confirmed': '۱۲ب۳۴۵-۶۷',
                'confidence_score': 0.95,
                'was_edited': False,
                'was_auto_approved': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(response.data['gate_event_id'])
        self.assertIsNotNone(response.data['session_id'])
        self.assertEqual(response.data['payment_status'], 'parked')

        session = ParkingSession.objects.get(id=response.data['session_id'])
        self.assertEqual(session.status, 'parked')
        self.assertEqual(session.plate, self.plate)

    def test_lookup_plate_returns_wallet_balance(self):
        ParkingSession.objects.create(
            plate=self.plate,
            entry_time=timezone.now(),
            status='parked',
        )

        response = self.client.get(
            '/api/parking/plates/lookup/',
            {'plate': '۱۲ب۳۴۵-۶۷'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['is_registered'])
        self.assertEqual(response.data['wallet_balance'], 100000)
        self.assertTrue(response.data['has_active_session'])
