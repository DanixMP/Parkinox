# WalletService Usage Guide

This document provides examples of how to use the `WalletService` class for wallet operations.

## Overview

The `WalletService` provides four main methods for wallet operations:
- `get_balance(user_id)` - Get current wallet balance
- `topup(wallet_id, amount, operator_id)` - Add funds to a wallet
- `deduct_fee(wallet_id, amount, session_id)` - Deduct parking fees
- `check_sufficient_balance(user_id, required_amount)` - Check if balance is sufficient

All balance-modifying operations use database transactions for atomicity.

## Import

```python
from wallets.services import WalletService, InsufficientFundsError
```

## Examples

### 1. Get Wallet Balance

```python
# Get balance for a user
user_id = 123
balance = WalletService.get_balance(user_id)
print(f"Current balance: {balance} Toman")
```

### 2. Top-up Wallet

```python
# Operator adds funds to a student's wallet
wallet_id = 456
amount = 50000  # 50,000 Toman
operator_id = 789

try:
    transaction = WalletService.topup(
        wallet_id=wallet_id,
        amount=amount,
        operator_id=operator_id
    )
    print(f"Top-up successful! Transaction ID: {transaction.id}")
    print(f"New balance: {WalletService.get_balance(user_id)} Toman")
except ValueError as e:
    print(f"Invalid amount: {e}")
except ObjectDoesNotExist as e:
    print(f"Wallet or operator not found: {e}")
```

### 3. Deduct Parking Fee

```python
# Deduct fee when a parking session is closed
wallet_id = 456
fee_amount = 20000  # 20,000 Toman
session_id = 123

try:
    transaction = WalletService.deduct_fee(
        wallet_id=wallet_id,
        amount=fee_amount,
        session_id=session_id
    )
    print(f"Fee deducted successfully! Transaction ID: {transaction.id}")
    print(f"Remaining balance: {WalletService.get_balance(user_id)} Toman")
except InsufficientFundsError as e:
    print(f"Insufficient balance: {e}")
    # Handle unpaid session - set status to 'unpaid'
except ValueError as e:
    print(f"Invalid amount: {e}")
except ObjectDoesNotExist as e:
    print(f"Wallet not found: {e}")
```

### 4. Check Sufficient Balance

```python
# Check if user has enough balance before attempting deduction
user_id = 123
required_amount = 20000

if WalletService.check_sufficient_balance(user_id, required_amount):
    print("Balance is sufficient")
    # Proceed with fee deduction
else:
    print("Insufficient balance")
    # Handle unpaid session
```

### 5. Complete Parking Exit Flow

```python
from wallets.services import WalletService, InsufficientFundsError
from django.core.exceptions import ObjectDoesNotExist

def process_parking_exit(user_id, wallet_id, fee_amount, session_id):
    """
    Process parking exit with automatic wallet payment.
    
    Returns:
        tuple: (success: bool, message: str, status: str)
    """
    try:
        # Check if balance is sufficient
        if not WalletService.check_sufficient_balance(user_id, fee_amount):
            return (False, "Insufficient balance", "unpaid")
        
        # Deduct fee
        transaction = WalletService.deduct_fee(
            wallet_id=wallet_id,
            amount=fee_amount,
            session_id=session_id
        )
        
        new_balance = WalletService.get_balance(user_id)
        
        return (
            True,
            f"Payment successful. Remaining balance: {new_balance} Toman",
            "completed"
        )
        
    except InsufficientFundsError:
        return (False, "Insufficient balance", "unpaid")
    except ObjectDoesNotExist as e:
        return (False, f"Error: {e}", "error")
    except Exception as e:
        return (False, f"Unexpected error: {e}", "error")
```

## Error Handling

### InsufficientFundsError

Raised when attempting to deduct more than the available balance:

```python
try:
    WalletService.deduct_fee(wallet_id, amount, session_id)
except InsufficientFundsError as e:
    # Balance is insufficient
    # Set session status to 'unpaid'
    # Require cash payment
    pass
```

### ValueError

Raised when amount is negative or zero:

```python
try:
    WalletService.topup(wallet_id, -1000, operator_id)
except ValueError as e:
    # Invalid amount provided
    pass
```

### ObjectDoesNotExist

Raised when wallet or user doesn't exist:

```python
from django.core.exceptions import ObjectDoesNotExist

try:
    balance = WalletService.get_balance(99999)
except ObjectDoesNotExist as e:
    # User or wallet not found
    pass
```

## Atomicity Guarantees

All balance-modifying operations (`topup` and `deduct_fee`) are atomic:

- Both the wallet balance update and transaction record creation succeed together
- If either operation fails, both are rolled back
- Uses Django's `@transaction.atomic` decorator
- Uses `select_for_update()` for row-level locking to prevent race conditions

Example of atomicity:

```python
from django.db import transaction

# This is handled automatically by the service
@transaction.atomic
def topup(wallet_id, amount, operator_id):
    wallet = Wallet.objects.select_for_update().get(id=wallet_id)
    wallet.balance += amount
    wallet.save()
    
    txn = WalletTransaction.objects.create(...)
    
    # Both operations succeed or both fail
    return txn
```

## Requirements Satisfied

- **5.1**: Get balance and increase balance on top-up
- **5.2**: Create transaction record with type 'topup'
- **5.3**: Record operator ID who performed top-up
- **5.4**: Return updated balance within 1 second
- **5.5**: Reject negative or zero amounts
- **18.1**: Deduct fee from wallet for registered users
- **18.2**: Create transaction record with type 'fee'
- **18.6**: Do not deduct when balance insufficient
- **18.7**: Atomic wallet deduction and transaction creation
- **52.1**: Single database transaction for atomicity
- **52.2**: Update session and create gate event links atomically
