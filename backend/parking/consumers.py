"""
WebSocket consumers for the parking app.

This module contains the WebSocket consumer for real-time communication
with operator panels.

Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 21.6, 23.2, 24.1, 24.2, 24.3, 24.4,
             25.1, 25.2, 25.3, 25.4, 25.5, 53.4, 65.1, 65.2, 65.3,
             75.1, 75.2, 75.3, 75.4, 75.5, 98.1, 98.2, 98.4
"""

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from zoneinfo import ZoneInfo
import datetime
import json
import logging

from .models import GateEvent, ParkingSession
from .services import ParkingSessionService
from .gate_event_service import confirm_gate_event, reject_gate_event

User = get_user_model()
logger = logging.getLogger(__name__)


class ParkingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for operator panel real-time communication.
    
    Handles:
    - JWT authentication on connection
    - Gate event confirmations and rejections
    - Real-time statistics broadcasting
    - Heartbeat ping/pong messages
    - Cash payment recording
    
    Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 21.6, 23.2, 24.1, 24.2, 24.3, 24.4,
                 75.1, 75.2, 75.3, 75.4, 75.5, 98.1, 98.2, 98.4
    """
    
    async def connect(self):
        """
        Handle WebSocket connection with JWT authentication.
        
        Authenticates the connection using JWT token from query parameters,
        then adds the authenticated connection to the 'operators' channel group.
        
        Requirements:
        - 21.1: Establish WebSocket connection
        - 21.2: Authenticate using JWT access token
        - 21.3: Display connected status indicator
        - 21.4: Display disconnected status on failure
        """
        # Extract token from query parameters
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        token = None
        
        # Parse query string for token parameter
        for param in query_string.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                if key == 'token':
                    token = value
                    break
        
        if not token:
            logger.warning("WebSocket connection rejected: No token provided")
            await self.close(code=4001)
            return
        
        # Validate JWT token
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            
            # Get user from database
            user = await self.get_user(user_id)
            
            if not user:
                logger.warning(f"WebSocket connection rejected: User {user_id} not found")
                await self.close(code=4002)
                return
            
            if not user.is_active:
                logger.warning(f"WebSocket connection rejected: User {user_id} is inactive")
                await self.close(code=4003)
                return
            
            # Check if user has operator or admin role
            if user.role not in ['operator', 'admin']:
                logger.warning(f"WebSocket connection rejected: User {user_id} is not an operator or admin")
                await self.close(code=4004)
                return
            
            # Store user in scope
            self.scope['user'] = user
            self.user = user
            
            # Accept connection
            await self.accept()
            
            # Add to operators channel group
            await self.channel_layer.group_add(
                'operators',
                self.channel_name
            )
            
            logger.info(f"WebSocket connection established for user {user.id} ({user.full_name})")
            
        except (TokenError, InvalidToken) as e:
            logger.warning(f"WebSocket connection rejected: Invalid token - {str(e)}")
            await self.close(code=4005)
            return
        except Exception as e:
            logger.error(f"WebSocket connection error: {str(e)}")
            await self.close(code=4000)
            return
    
    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection with cleanup.
        
        Removes the connection from the 'operators' channel group and
        performs any necessary cleanup.
        
        Requirements:
        - 21.4: Handle connection loss
        - 21.6: Run WebSocket in background thread
        """
        # Remove from operators channel group
        if hasattr(self, 'user'):
            await self.channel_layer.group_discard(
                'operators',
                self.channel_name
            )
            logger.info(f"WebSocket disconnected for user {self.user.id} (code: {close_code})")
        else:
            logger.info(f"WebSocket disconnected (code: {close_code})")
    
    async def receive(self, text_data):
        """
        Handle incoming WebSocket messages.
        
        Validates message structure and routes to appropriate handler based on type.
        
        Supported message types:
        - gate_event.confirm: Operator approves a detection
        - gate_event.reject: Operator rejects a detection
        - session.cash_payment: Record cash payment for unpaid session
        - ping: Heartbeat message
        
        Requirements:
        - 21.5: Handle incoming messages
        - 23.2: Respond to ping with pong
        - 24.1: Send gate_event.confirm via WebSocket
        - 24.2: Include all required fields
        - 75.1: Validate all incoming messages have 'type' field
        - 75.2: Validate required fields for each message type
        - 75.3: Send error responses for malformed messages
        """
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.warning("Received invalid JSON")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
            return
        
        # Validate message has 'type' field (Requirement 75.1)
        message_type = data.get('type')
        if not message_type:
            logger.warning("Received message without 'type' field")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': "Message must include 'type' field"
            }))
            return
        
        # Route to appropriate handler
        if message_type == 'ping':
            await self.handle_ping(data)
        elif message_type == 'gate_event.confirm':
            await self.handle_gate_event_confirm(data)
        elif message_type == 'gate_event.reject':
            await self.handle_gate_event_reject(data)
        elif message_type == 'session.cash_payment':
            await self.handle_cash_payment(data)
        elif message_type == 'session.waive_fee':
            await self.handle_waive_fee(data)
        else:
            logger.warning(f"Unknown message type: {message_type}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Unknown message type: {message_type}"
            }))
    
    async def handle_ping(self, data):
        """
        Handle heartbeat ping message.
        
        Responds with pong message to confirm connection is alive.
        
        Requirements:
        - 23.2: Respond to ping with pong
        """
        await self.send(text_data=json.dumps({
            'type': 'pong'
        }))
    
    async def handle_gate_event_confirm(self, data):
        """
        Handle gate event confirmation from operator.
        
        Creates a GateEvent record, matches plate to user, creates or closes
        parking session, and sends acknowledgment with session details.
        
        Requirements:
        - 24.1: Send gate_event.confirm message via WebSocket
        - 24.2: Include camera ID, raw plate, confirmed plate, edit status, etc.
        - 24.3: Create gate event record
        - 24.4: Send gate_event.ack message back
        - 75.2: Validate required fields
        - 75.3: Send error responses for malformed messages
        """
        # Validate required fields (Requirement 75.2)
        required_fields = ['camera_id', 'direction', 'plate_raw', 'plate_confirmed']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Missing required fields: {', '.join(missing_fields)}"
            }))
            return
        
        # Extract data
        camera_id = data.get('camera_id')
        direction = data.get('direction')
        plate_raw = data.get('plate_raw')
        plate_confirmed = data.get('plate_confirmed')
        confidence_score = data.get('confidence_score')
        was_edited = data.get('was_edited', False)
        was_auto_approved = data.get('was_auto_approved', False)
        
        # Validate direction
        if direction not in ['entry', 'exit']:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': "Direction must be 'entry' or 'exit'"
            }))
            return
        
        try:
            # Create gate event and process session
            result = await self.create_gate_event_and_session(
                camera_id=camera_id,
                direction=direction,
                plate_raw=plate_raw,
                plate_confirmed=plate_confirmed,
                confidence_score=confidence_score,
                was_edited=was_edited,
                was_auto_approved=was_auto_approved,
                operator_id=self.user.id
            )
            
            # Send acknowledgment (Requirement 24.4, 24.5)
            await self.send(text_data=json.dumps({
                'type': 'gate_event.ack',
                'event_id': result['event_id'],
                'session_id': result['session_id'],
                'matched_user': result['matched_user'],
                'fee': result['fee'],
                'payment_status': result['payment_status'],
                'wallet_balance': result['wallet_balance'],
                'wallet_sufficient': result['wallet_sufficient']
            }))

            # Broadcast statistics update to all connected operators (Requirement 25.1)
            await self.broadcast_stats()

            logger.info(f"Gate event confirmed: {direction} - {plate_confirmed}")
            
        except Exception as e:
            logger.error(f"Error processing gate event: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Error processing gate event: {str(e)}"
            }))
    
    async def handle_gate_event_reject(self, data):
        """
        Handle gate event rejection from operator.
        
        Creates a GateEvent record marked as rejected.
        
        Requirements:
        - 75.2: Validate required fields
        - 75.3: Send error responses for malformed messages
        """
        # Validate required fields
        required_fields = ['camera_id', 'direction', 'plate_raw']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Missing required fields: {', '.join(missing_fields)}"
            }))
            return
        
        # Extract data
        camera_id = data.get('camera_id')
        direction = data.get('direction')
        plate_raw = data.get('plate_raw')
        confidence_score = data.get('confidence_score')
        
        # Validate direction
        if direction not in ['entry', 'exit']:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': "Direction must be 'entry' or 'exit'"
            }))
            return
        
        try:
            # Create rejected gate event
            event_id = await self.create_rejected_gate_event(
                camera_id=camera_id,
                direction=direction,
                plate_raw=plate_raw,
                confidence_score=confidence_score,
                operator_id=self.user.id
            )
            
            # Send acknowledgment
            await self.send(text_data=json.dumps({
                'type': 'gate_event.reject_ack',
                'event_id': event_id
            }))
            
            logger.info(f"Gate event rejected: {direction} - {plate_raw}")
            
        except Exception as e:
            logger.error(f"Error rejecting gate event: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Error rejecting gate event: {str(e)}"
            }))
    
    async def handle_cash_payment(self, data):
        """
        Handle cash payment recording for unpaid session.
        
        Requirements:
        - 75.2: Validate required fields
        - 75.3: Send error responses for malformed messages
        """
        # Validate required fields
        required_fields = ['session_id']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Missing required fields: {', '.join(missing_fields)}"
            }))
            return
        
        session_id = data.get('session_id')
        notes = data.get('notes', '')
        
        try:
            # Record cash payment
            session = await self.record_cash_payment(
                session_id=session_id,
                operator_id=self.user.id,
                notes=notes
            )
            
            # Send acknowledgment
            await self.send(text_data=json.dumps({
                'type': 'session.cash_payment_ack',
                'session_id': session.id,
                'status': session.status,
                'payment_method': session.payment_method
            }))

            # Broadcast statistics update after session state change (Requirement 65.1)
            await self.broadcast_stats()

            logger.info(f"Cash payment recorded for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error recording cash payment: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Error recording cash payment: {str(e)}"
            }))
    
    async def broadcast_stats(self):
        """
        Broadcast statistics update to all connected operator panels.

        Calculates current parking statistics using Asia/Tehran timezone for
        today's date boundaries, then sends a stats.update message to the
        'operators' channel group.

        Statistics included:
        - entries_today: Number of entry gate events today
        - exits_today: Number of exit gate events today
        - currently_parked: Number of sessions with status='parked'
        - revenue_today: Sum of fee_charged for completed/waived sessions today
        - capacity: Total parking capacity (from settings or default 100)

        Called after every session state change.

        Requirements:
        - 25.1: Broadcast stats.update when session changes state
        - 25.2: Include entries_today, exits_today, currently_parked, revenue_today, capacity
        - 25.4: Calculate statistics based on current date in Asia/Tehran timezone
        - 25.5: Count only completed and waived sessions for revenue
        - 53.4: Use Asia/Tehran timezone for date boundaries
        - 65.1: Trigger after create_entry_session / close_exit_session
        - 65.2: Trigger after record_cash_payment
        - 65.3: Trigger after waive_fee
        """
        try:
            stats = await self.get_stats()

            await self.channel_layer.group_send(
                'operators',
                {
                    'type': 'stats.update',
                    'data': stats
                }
            )

            logger.info(
                f"Stats broadcast: entries={stats['entries_today']}, "
                f"exits={stats['exits_today']}, "
                f"parked={stats['currently_parked']}, "
                f"revenue={stats['revenue_today']}"
            )
        except Exception as e:
            logger.error(f"Error broadcasting stats: {str(e)}")

    async def stats_update(self, event):
        """
        Channel layer handler for stats.update group messages.

        Forwards the stats.update message to the WebSocket client.

        Requirements:
        - 25.1: Deliver stats.update to all connected Operator_Panels
        """
        await self.send(text_data=json.dumps({
            'type': 'stats.update',
            'data': event['data']
        }))

    async def handle_waive_fee(self, data):
        """
        Handle fee waiver for a parking session.

        Requirements:
        - 75.2: Validate required fields
        - 75.3: Send error responses for malformed messages
        - 65.3: Broadcast stats after waive_fee
        """
        # Validate required fields
        required_fields = ['session_id']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Missing required fields: {', '.join(missing_fields)}"
            }))
            return

        session_id = data.get('session_id')

        try:
            session = await self.waive_fee(
                session_id=session_id,
                operator_id=self.user.id
            )

            # Send acknowledgment
            await self.send(text_data=json.dumps({
                'type': 'session.waive_fee_ack',
                'session_id': session.id,
                'status': session.status,
                'fee_charged': int(session.fee_charged)
            }))

            # Broadcast statistics update after session state change (Requirement 65.3)
            await self.broadcast_stats()

            logger.info(f"Fee waived for session {session_id}")

        except Exception as e:
            logger.error(f"Error waiving fee: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f"Error waiving fee: {str(e)}"
            }))

    # Database operations (wrapped with database_sync_to_async)

    @database_sync_to_async
    def get_user(self, user_id):
        """Get user by ID from database."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
    
    @database_sync_to_async
    def create_gate_event_and_session(self, camera_id, direction, plate_raw,
                                      plate_confirmed, confidence_score,
                                      was_edited, was_auto_approved, operator_id):
        """Create gate event and process parking session (shared with REST API)."""
        return confirm_gate_event(
            operator_id=operator_id,
            camera_id=camera_id,
            direction=direction,
            plate_raw=plate_raw,
            plate_confirmed=plate_confirmed,
            confidence_score=confidence_score,
            was_edited=was_edited,
            was_auto_approved=was_auto_approved,
        )

    @database_sync_to_async
    def create_rejected_gate_event(self, camera_id, direction, plate_raw,
                                   confidence_score, operator_id):
        """Create a rejected gate event."""
        return reject_gate_event(
            operator_id=operator_id,
            camera_id=camera_id,
            direction=direction,
            plate_raw=plate_raw,
            confidence_score=confidence_score,
        )
    
    @database_sync_to_async
    def record_cash_payment(self, session_id, operator_id, notes):
        """Record cash payment for unpaid session."""
        return ParkingSessionService.record_cash_payment(
            session_id=session_id,
            operator_id=operator_id,
            notes=notes
        )

    @database_sync_to_async
    def waive_fee(self, session_id, operator_id):
        """Waive fee for a parking session."""
        return ParkingSessionService.waive_fee(
            session_id=session_id,
            operator_id=operator_id
        )

    @database_sync_to_async
    def get_stats(self):
        """
        Calculate current parking statistics using Asia/Tehran timezone.

        Returns a dict with:
        - entries_today: count of entry GateEvents created today (Tehran time)
        - exits_today: count of exit GateEvents created today (Tehran time)
        - currently_parked: count of ParkingSessions with status='parked'
        - revenue_today: sum of fee_charged for completed/waived sessions today
        - capacity: total parking capacity from settings (default 100)

        Requirements:
        - 25.2: Include all required statistics fields
        - 25.4: Use Asia/Tehran timezone for date boundaries
        - 25.5: Count only completed and waived sessions for revenue
        - 53.4: Use Asia/Tehran timezone for date boundaries
        """
        tehran_tz = ZoneInfo('Asia/Tehran')

        # Get today's date in Tehran timezone
        now_tehran = datetime.datetime.now(tehran_tz)
        today_tehran = now_tehran.date()

        # Calculate start and end of today in Tehran time, then convert to UTC
        # for database queries (Django stores timestamps in UTC)
        today_start_tehran = datetime.datetime.combine(
            today_tehran,
            datetime.time.min,
            tzinfo=tehran_tz
        )
        today_end_tehran = datetime.datetime.combine(
            today_tehran,
            datetime.time.max,
            tzinfo=tehran_tz
        )

        # Count entry gate events today (Requirement 25.2)
        entries_today = GateEvent.objects.filter(
            direction='entry',
            was_rejected=False,
            created_at__gte=today_start_tehran,
            created_at__lte=today_end_tehran
        ).count()

        # Count exit gate events today (Requirement 25.2)
        exits_today = GateEvent.objects.filter(
            direction='exit',
            was_rejected=False,
            created_at__gte=today_start_tehran,
            created_at__lte=today_end_tehran
        ).count()

        # Count currently parked vehicles (Requirement 25.2)
        currently_parked = ParkingSession.objects.filter(
            status='parked'
        ).count()

        # Calculate revenue today from completed and waived sessions (Requirement 25.5)
        revenue_result = ParkingSession.objects.filter(
            status__in=['completed', 'waived'],
            exit_time__gte=today_start_tehran,
            exit_time__lte=today_end_tehran
        ).aggregate(total=Sum('fee_charged'))

        revenue_today = int(revenue_result['total'] or 0)

        # Get capacity from settings (Requirement 25.2)
        capacity = getattr(settings, 'PARKING_CAPACITY', 100)

        return {
            'entries_today': entries_today,
            'exits_today': exits_today,
            'currently_parked': currently_parked,
            'revenue_today': revenue_today,
            'capacity': capacity
        }
