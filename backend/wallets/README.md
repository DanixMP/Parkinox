# Wallets App

This Django app manages digital wallets and wallet transactions for the Parkinox Smart University Parking System.

## Models

### Wallet

Digital wallet for parking fee payments. Each user has exactly one wallet, which is automatically created when the user is created via a post_save signal.

**Fields:**
- `user`: OneToOneField to User model
- `balance`: Non-negative decimal balance in Toman (enforced by database CHECK constraint)
- `last_updated`: Timestamp of last wallet update (auto-updated)

**Requirements:** 3.1, 3.2, 3.3, 3.4, 3.5

### WalletTransaction

Immutable transaction log for wallet operations. Transactions cannot be modified or deleted after creation.

**Fields:**
- `wallet`: ForeignKey to Wallet
- `amount`: Positive decimal amount in Toman
- `type`: Transaction type (topup, fee, refund)
- `description`: Optional transaction description
- `performed_by`: User who performed the transaction (operator for top-ups)
- `reference_code`: Unique reference code
- `session`: ForeignKey to ParkingSession (will be added in a future migration when parking app is created)
- `created_at`: Transaction timestamp

**Requirements:** 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7

## Signals

### create_user_wallet

Post-save signal that automatically creates a wallet with zero balance when a new User is created.

**Requirement:** 3.1

## Future Enhancements

The `session` field on WalletTransaction will be added in a future migration once the `parking` app is created. This field will link fee transactions to their corresponding parking sessions.

## Testing

Run tests with:
```bash
python manage.py test wallets
```

All tests verify:
- Automatic wallet creation on user creation
- Non-negative balance constraint
- Transaction creation (topup, fee, refund)
- Transaction immutability
- Unique reference codes
