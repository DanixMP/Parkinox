# Task 5.1 Implementation Summary

## Task: Create utils/fee_calculator.py with calculate_fee() function

### Implementation Details

Created `backend/utils/fee_calculator.py` with the following components:

#### 1. RATES Constants
```python
RATES = {
    "per_hour_toman": 5000,
    "daily_max_toman": 40000,
    "grace_period_minutes": 10,
    "student_discount": 0.8  # 20% off
}
```

#### 2. calculate_fee() Function
The function implements the following algorithm using **integer arithmetic only**:

1. **Calculate duration in minutes** from entry_time and exit_time
2. **Apply grace period**: Return 0 if duration ≤ 10 minutes
3. **Calculate hours** using ceiling division: `(minutes + 59) // 60`
4. **Calculate base fee**: `hours * 5000` Toman
5. **Apply daily cap**: `min(fee, 40000)` Toman
6. **Apply student discount** if is_student: `(fee * 80) // 100`
7. **Return integer** Toman amount

#### Key Design Decisions

- **Integer Arithmetic Only**: All calculations use integer division to avoid floating-point precision issues
- **Ceiling Division**: `(minutes + 59) // 60` rounds up any partial hour to the next full hour
- **Student Discount**: Applied as `(fee * 80) // 100` instead of `fee * 0.8` to maintain integer arithmetic
- **Order of Operations**: Daily cap is applied before student discount (as per requirements)

### Test Coverage

Created comprehensive unit tests in `backend/utils/test_fee_calculator.py`:

- ✅ Grace period (≤10 minutes = free)
- ✅ One hour fee calculation
- ✅ Partial hour rounding up
- ✅ Daily cap enforcement
- ✅ Student discount application
- ✅ Student discount with daily cap
- ✅ Invalid input validation (exit before entry)
- ✅ Zero duration handling
- ✅ Integer arithmetic verification
- ✅ RATES constants validation

**All 10 tests pass successfully.**

### Requirements Validated

This implementation validates the following requirements:

- **16.1**: Fee calculation based on entry and exit timestamps
- **16.2**: 5000 Toman per hour or fraction thereof
- **16.3**: Maximum daily fee cap of 40000 Toman
- **16.4**: Grace period of 10 minutes (zero fee)
- **16.5**: 20% student discount application
- **16.6**: Full fee for guests (no discount)
- **16.7**: Partial hours rounded up
- **66.1-66.2**: Grace period implementation
- **67.1-67.5**: Daily cap implementation
- **68.1-68.4**: Student discount implementation
- **69.1-69.5**: Hourly fee calculation
- **97.2**: Integer arithmetic for consistency
- **97.3**: Rounding to nearest Toman
- **97.4**: Fixed order of fee calculation steps

### Integration

Updated `backend/utils/__init__.py` to export:
- `calculate_fee` function
- `RATES` constants

The module can now be imported as:
```python
from backend.utils import calculate_fee, RATES
```

### Example Usage

```python
from datetime import datetime, timedelta
from backend.utils import calculate_fee

entry = datetime(2024, 1, 1, 10, 0, 0)

# Grace period - free
exit = entry + timedelta(minutes=10)
fee = calculate_fee(entry, exit, False)  # Returns: 0

# 2 hours, non-student
exit = entry + timedelta(hours=2)
fee = calculate_fee(entry, exit, False)  # Returns: 10000

# 2 hours, student (20% discount)
fee = calculate_fee(entry, exit, True)  # Returns: 8000

# 10 hours, capped at daily max
exit = entry + timedelta(hours=10)
fee = calculate_fee(entry, exit, False)  # Returns: 40000

# 10 hours, student (cap then discount)
fee = calculate_fee(entry, exit, True)  # Returns: 32000
```

### Status

✅ **Task 5.1 Complete**

- Fee calculator module created
- All requirements implemented
- Integer arithmetic enforced
- Comprehensive tests written and passing
- Module integrated into utils package
