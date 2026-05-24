# Plates App

## Overview

The `plates` app manages license plate registrations for the Parkinox smart parking system. It stores Iranian vehicle license plates in normalized format and associates them with user accounts.

## Models

### Plate Model

Stores registered license plates associated with users.

**Fields:**
- `id`: Auto-incrementing primary key
- `user`: Foreign key to User model (CASCADE delete)
- `plate_number`: Normalized plate format: `[۰-۹]{2}[letter][۰-۹]{3}-[۰-۹]{2}`
- `is_primary`: Boolean indicating if this is the user's primary plate
- `is_verified`: Boolean indicating if the plate has been verified by an operator
- `is_active`: Boolean indicating if the plate is currently active
- `created_at`: Timestamp when the plate was registered

**Constraints:**
1. **Unique Together**: `(user, plate_number)` - A user cannot register the same plate twice
2. **One Primary Per User**: Only one plate can be marked as primary and active per user
3. **Plate Format Validation**: All plates must match the Iranian plate format after normalization

**Indexes:**
1. `plates_active_plate_idx`: Index on `plate_number` WHERE `is_active=TRUE` for fast active plate lookups
2. `plates_user_id_*`: Indexes for user-based queries
3. `plates_user_id_is_primary_*`: Index for finding primary plates

**Automatic Behaviors:**
- When a user registers their first plate, it is automatically marked as primary
- When a plate is set as primary, all other primary plates for that user are automatically unmarked
- Plate numbers are automatically normalized using the `plate_normalizer` utility before saving

## Requirements Validated

This implementation validates the following requirements:

- **6.1**: Store plate number in normalized format
- **6.2**: Prevent duplicate plate registrations for the same user
- **6.3**: Allow a user to register multiple plates
- **6.4**: Mark first plate as primary automatically
- **6.5**: Allow only one primary plate per user at any time
- **6.6**: Support marking plates as active or inactive
- **6.7**: Record timestamp when each plate is registered
- **52.5**: (Related to plate lookup functionality)
- **99.1**: (Related to system-wide plate management)

## Usage Examples

### Creating a Plate

```python
from plates.models import Plate
from accounts.models import User

user = User.objects.get(phone='+989123456789')

# Create a plate (will be normalized automatically)
plate = Plate.objects.create(
    user=user,
    plate_number='12ب345-67'  # Latin digits will be converted to Persian
)

# The plate_number is now: '۱۲ب۳۴۵-۶۷'
print(plate.plate_number)  # Output: ۱۲ب۳۴۵-۶۷
print(plate.is_primary)    # Output: True (if this is the first plate)
```

### Querying Plates

```python
# Get all active plates for a user
active_plates = Plate.objects.filter(user=user, is_active=True)

# Get the primary plate for a user
primary_plate = Plate.objects.get(user=user, is_primary=True, is_active=True)

# Lookup a plate by number (active plates only)
plate = Plate.objects.get(plate_number='۱۲ب۳۴۵-۶۷', is_active=True)
```

### Setting a New Primary Plate

```python
# Get a non-primary plate
plate = Plate.objects.get(id=2)

# Set it as primary (will automatically unset other primary plates)
plate.is_primary = True
plate.save()
```

## Admin Interface

The Plate model is registered in the Django admin interface with the following features:

- List display: plate_number, user, is_primary, is_verified, is_active, created_at
- Filters: is_primary, is_verified, is_active, created_at
- Search: plate_number, user full_name, user phone, user student_id
- Organized fieldsets for easy editing

## Database Schema

```sql
CREATE TABLE "plates" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "plate_number" varchar(20) NOT NULL,
    "is_primary" bool NOT NULL,
    "is_verified" bool NOT NULL,
    "is_active" bool NOT NULL,
    "created_at" datetime NOT NULL,
    "user_id" integer NOT NULL REFERENCES "users" ("id") DEFERRABLE INITIALLY DEFERRED
);

-- Unique constraint: one primary plate per user
CREATE UNIQUE INDEX "plates_one_primary_per_user" 
ON "plates" ("user_id") 
WHERE ("is_active" AND "is_primary");

-- Unique constraint: no duplicate plates per user
CREATE UNIQUE INDEX "plates_user_id_plate_number_85a8a993_uniq" 
ON "plates" ("user_id", "plate_number");

-- Index for active plate lookups
CREATE INDEX "plates_active_plate_idx" 
ON "plates" ("plate_number") 
WHERE "is_active";
```

## Testing

Run the test script to verify the Plate model functionality:

```bash
python test_plates.py
```

The test script verifies:
- Database schema and indexes
- Model creation and validation
- Auto-primary plate assignment
- Unique constraints
- Plate normalization
- Invalid plate rejection

## Integration with Other Apps

The Plates app integrates with:

- **accounts**: Foreign key relationship to User model
- **utils**: Uses `plate_normalizer.normalize_plate()` for plate validation
- **parking** (future): Will be referenced by GateEvent and ParkingSession models

## Next Steps

Future enhancements may include:

1. Plate verification workflow for operators
2. Plate history tracking (when plates are deactivated/reactivated)
3. Bulk plate import functionality
4. Plate ownership transfer between users
5. Integration with external vehicle registration databases
