from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import CheckConstraint, Q, F
from accounts.models import User


class Wallet(models.Model):
    """
    Digital wallet for parking fee payments.
    Auto-created via post_save signal when User is created.
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
    """
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='wallet',
        help_text="User who owns this wallet"
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Wallet balance in Toman (non-negative)"
    )
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of last wallet update"
    )
    
    class Meta:
        db_table = 'wallets'
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'
        constraints = [
            CheckConstraint(
                check=Q(balance__gte=0),
                name='wallet_balance_non_negative'
            ),
        ]
        indexes = [
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Wallet for {self.user.full_name} - Balance: {self.balance} Toman"


class WalletTransaction(models.Model):
    """
    Immutable transaction log for wallet operations.
    
    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    TRANSACTION_TYPE_CHOICES = [
        ('topup', 'Top-up'),
        ('fee', 'Fee'),
        ('refund', 'Refund'),
    ]
    
    id = models.AutoField(primary_key=True)
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name='transactions',
        help_text="Wallet this transaction belongs to"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(1)],
        help_text="Transaction amount in Toman (positive)"
    )
    type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPE_CHOICES,
        help_text="Transaction type: topup, fee, or refund"
    )
    description = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Optional transaction description"
    )
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_transactions',
        help_text="User who performed this transaction (operator for top-ups)"
    )
    reference_code = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text="Unique reference code for this transaction"
    )
    session = models.ForeignKey(
        'parking.ParkingSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='wallet_transactions',
        help_text='Parking session linked to this transaction (for fee transactions)',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Transaction timestamp"
    )
    
    class Meta:
        db_table = 'wallet_transactions'
        verbose_name = 'Wallet Transaction'
        verbose_name_plural = 'Wallet Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['type']),
            models.Index(fields=['reference_code']),
        ]
    
    def __str__(self):
        return f"{self.type.upper()} - {self.amount} Toman - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        """
        Prevent modification of existing transaction records.
        Requirement 4.7: Immutable transaction log.
        """
        if self.pk is not None:
            raise ValueError("Transaction records cannot be modified after creation")
        super().save(*args, **kwargs)
