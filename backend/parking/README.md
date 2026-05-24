# Parking App

This Django app manages gate events and parking sessions for the Parkinox smart parking system.

## Models

### GateEvent

Immutable audit log of all camera detections at entry and exit gates. This model records every gate event and should **NEVER** be updated or deleted, only inserted.

**Fields:**
- `camera_id`: Camera identifier (e.g., 'entry', 'exit')
- `direction`: Direction of vehicle movement ('entry' or 'exit')
- `plate_raw`: Raw plate number as detected by OCR before operator confirmation
- `plate_confirmed`: Confirmed plate number after operator approval/editing
- `confidence_score`: OCR confidence score (0.0000 to 1.0000)
- `plate_image_path`: Path to stored plate image file
- `was_edited`: Whether the operator manually edited the detected plate number
- `was_auto_approved`: Whether the event was auto-approved after timeout (15 seconds)
- `was_rejected`: Whether the operator rejected this detection
- `operator`: Foreign key to User who processed this gate event
- `matched_user`: Foreign key to User associated with the detected plate (if registered)
- `matched_plate`: Foreign key to Plate registration associated with this detection (if registered)
- `session`: Foreign key to ParkingSession associated with this gate event
- `created_at`: Timestamp when gate event was recorded (UTC)

**Indexes:**
- `plate_confirmed`: For plate lookups
- `created_at` (descending): For chronological queries
- `(direction, created_at)` (descending): For direction-based chronological queries

**Immutability:**
- Updates are prevented by overriding the `save()` method
- Deletes are prevented by overriding the `delete()` method
- Admin interface is read-only (no change or delete permissions)

**Requirements:** 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 73.1, 73.2, 73.3, 73.4, 99.2

### ParkingSession

Placeholder model for parking sessions. This will be fully implemented in task 6.2.

**Fields:**
- `id`: Primary key
- `created_at`: Timestamp when session was created

## Usage

### Creating a Gate Event

```python
from parking.models import GateEvent
from accounts.models import User
from plates.models import Plate
from decimal import Decimal

# Get operator and matched user/plate
operator = User.objects.get(phone='+989123456789')
user = User.objects.get(phone='+989123456790')
plate = Plate.objects.get(plate_number='۱۲ب۳۴۵-۶۷')

# Create entry gate event
gate_event = GateEvent.objects.create(
    camera_id='entry',
    direction='entry',
    plate_raw='۱۲ب۳۴۵-۶۷',
    plate_confirmed='۱۲ب۳۴۵-۶۷',
    confidence_score=Decimal('0.9500'),
    was_edited=False,
    was_auto_approved=False,
    was_rejected=False,
    operator=operator,
    matched_user=user,
    matched_plate=plate
)
```

### Querying Gate Events

```python
# Get all entry events
entry_events = GateEvent.objects.filter(direction='entry')

# Get events for a specific plate
plate_events = GateEvent.objects.filter(plate_confirmed='۱۲ب۳۴۵-۶۷')

# Get recent events (ordered by created_at descending)
recent_events = GateEvent.objects.all().order_by('-created_at')[:10]

# Get events processed by a specific operator
operator_events = GateEvent.objects.filter(operator=operator)
```

## Testing

Run the test suite:

```bash
python manage.py test parking
```

Run specific test:

```bash
python manage.py test parking.tests.GateEventModelTest.test_create_entry_gate_event
```

## Admin Interface

The GateEvent model is registered in the Django admin interface with read-only access to enforce immutability. Operators and admins can view gate events but cannot modify or delete them.

Access the admin interface at: `/admin/parking/gateevent/`

## Migration

The initial migration creates the `gate_events` and `parking_sessions` tables with all required indexes and constraints.

Apply migrations:

```bash
python manage.py migrate parking
```

## Task Summary

**Task 6.1**: Create parking app with GateEvent model

**Status**: ✅ Complete

**Implementation:**
- Created Django app `parking`
- Implemented `GateEvent` model with all required fields
- Implemented `ParkingSession` placeholder model
- Added immutability enforcement (no updates/deletes)
- Created database indexes for performance
- Registered models in Django admin (read-only for GateEvent)
- Created comprehensive test suite
- Generated and applied database migration

**Files Created:**
- `backend/parking/models.py`
- `backend/parking/apps.py`
- `backend/parking/admin.py`
- `backend/parking/tests.py`
- `backend/parking/README.md`
- `backend/parking/migrations/0001_initial.py`

**Configuration Changes:**
- Added `'parking'` to `INSTALLED_APPS` in `backend/config/settings/base.py`
