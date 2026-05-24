from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import User
from plates.models import Plate


class GateEvent(models.Model):
    """
    Immutable audit log of all camera detections at entry and exit gates.
    
    This model records every gate event and should NEVER be updated or deleted,
    only inserted. It provides a complete audit trail of all vehicle movements.
    
    Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 73.1, 73.2, 73.3, 73.4, 99.2
    """
    
    DIRECTION_CHOICES = [
        ('entry', 'Entry'),
        ('exit', 'Exit'),
    ]
    
    id = models.AutoField(primary_key=True)
    
    # Camera and direction information
    camera_id = models.CharField(
        max_length=20,
        help_text="Camera identifier (e.g., 'entry', 'exit')"
    )
    direction = models.CharField(
        max_length=10,
        choices=DIRECTION_CHOICES,
        help_text="Direction of vehicle movement: 'entry' or 'exit'"
    )
    
    # Plate detection information
    plate_raw = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Raw plate number as detected by OCR before operator confirmation"
    )
    plate_confirmed = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Confirmed plate number after operator approval/editing"
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="OCR confidence score (0.0000 to 1.0000)"
    )
    plate_image_path = models.CharField(
        max_length=512,
        null=True,
        blank=True,
        help_text="Path to stored plate image file"
    )
    
    # Event processing metadata
    was_edited = models.BooleanField(
        default=False,
        help_text="Whether the operator manually edited the detected plate number"
    )
    was_auto_approved = models.BooleanField(
        default=False,
        help_text="Whether the event was auto-approved after timeout (15 seconds)"
    )
    was_rejected = models.BooleanField(
        default=False,
        help_text="Whether the operator rejected this detection"
    )
    
    # Foreign key relationships
    operator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_gate_events',
        help_text="Operator who processed this gate event"
    )
    matched_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_gate_events',
        help_text="User associated with the detected plate (if registered)"
    )
    matched_plate = models.ForeignKey(
        Plate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gate_events',
        help_text="Plate registration associated with this detection (if registered)"
    )
    session = models.ForeignKey(
        'ParkingSession',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='gate_events',
        help_text="Parking session associated with this gate event"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when gate event was recorded (UTC)"
    )
    
    class Meta:
        db_table = 'gate_events'
        verbose_name = 'Gate Event'
        verbose_name_plural = 'Gate Events'
        indexes = [
            # Index for plate lookups
            models.Index(fields=['plate_confirmed']),
            # Index for chronological queries
            models.Index(fields=['-created_at']),
            # Composite index for direction-based chronological queries
            models.Index(fields=['direction', '-created_at']),
        ]
        # Enforce immutability through permissions (no update/delete)
        default_permissions = ('add', 'view')
    
    def __str__(self):
        direction_indicator = "ورودی" if self.direction == 'entry' else "خروجی"
        plate_display = self.plate_confirmed or self.plate_raw or "نامشخص"
        return f"{direction_indicator} - {plate_display} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    def clean(self):
        """
        Validate gate event data.
        """
        # Validate direction
        if self.direction not in ['entry', 'exit']:
            raise ValidationError({
                'direction': 'Direction must be either "entry" or "exit"'
            })
        
        # Validate confidence score range
        if self.confidence_score is not None:
            if self.confidence_score < 0 or self.confidence_score > 1:
                raise ValidationError({
                    'confidence_score': 'Confidence score must be between 0 and 1'
                })
    
    def save(self, *args, **kwargs):
        """
        Override save to enforce immutability and validation.
        """
        # Enforce immutability: prevent updates to existing records
        if self.pk is not None:
            raise ValidationError(
                "Gate events are immutable and cannot be updated. "
                "Create a new gate event instead."
            )
        
        # Run validation
        self.full_clean()
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Override delete to enforce immutability.
        """
        raise ValidationError(
            "Gate events are immutable and cannot be deleted. "
            "They form an audit trail that must be preserved."
        )


class ParkingSession(models.Model):
    """
    Parking session tracking entry, exit, duration, and payment.
    
    This model tracks parking sessions from entry to exit, supporting both
    registered users (with plate FK) and guests (with guest_plate_number).
    
    Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 64.1, 64.2, 99.3
    """
    
    STATUS_CHOICES = [
        ('parked', 'Parked'),
        ('completed', 'Completed'),
        ('unpaid', 'Unpaid'),
        ('waived', 'Waived'),
        ('flagged', 'Flagged'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('wallet', 'Wallet'),
        ('cash', 'Cash'),
        ('waived', 'Waived'),
    ]
    
    id = models.AutoField(primary_key=True)
    
    # Plate information - either registered plate OR guest plate number
    plate = models.ForeignKey(
        Plate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='parking_sessions',
        help_text="Registered plate (if user is registered)"
    )
    guest_plate_number = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Plate number for guest vehicles (normalized format)"
    )
    
    # Gate event references
    entry_event = models.ForeignKey(
        'GateEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entry_sessions',
        help_text="Gate event that created this session"
    )
    exit_event = models.ForeignKey(
        'GateEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='exit_sessions',
        help_text="Gate event that closed this session"
    )
    
    # Time tracking
    entry_time = models.DateTimeField(
        help_text="Timestamp when vehicle entered (UTC)"
    )
    exit_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when vehicle exited (UTC)"
    )
    duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Total parking duration in minutes"
    )
    
    # Payment information
    fee_charged = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        help_text="Fee charged in Toman"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='parked',
        help_text="Current session status"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        null=True,
        blank=True,
        help_text="Payment method used (if paid)"
    )
    
    # Operator attribution
    collected_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collected_sessions',
        help_text="Operator who collected cash payment or waived fee"
    )
    
    # Additional information
    notes = models.TextField(
        null=True,
        blank=True,
        help_text="Optional notes from operator"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when session was created"
    )
    
    class Meta:
        db_table = 'parking_sessions'
        verbose_name = 'Parking Session'
        verbose_name_plural = 'Parking Sessions'
        indexes = [
            # Index for filtering non-completed sessions (Requirement 99.3)
            models.Index(
                fields=['status'],
                condition=~models.Q(status='completed'),
                name='parking_sess_active_idx'
            ),
            # Index for chronological queries (Requirement 99.3)
            models.Index(fields=['-entry_time']),
        ]
        constraints = [
            # Ensure either plate or guest_plate_number is populated
            models.CheckConstraint(
                check=(
                    models.Q(plate__isnull=False) | 
                    models.Q(guest_plate_number__isnull=False)
                ),
                name='parking_sess_plate_or_guest'
            ),
        ]
    
    def __str__(self):
        if self.plate:
            plate_display = self.plate.plate_number
        elif self.guest_plate_number:
            plate_display = f"{self.guest_plate_number} (مهمان)"
        else:
            plate_display = "نامشخص"
        
        status_display = self.get_status_display()
        return f"Session {self.id} - {plate_display} - {status_display}"
    
    def clean(self):
        """
        Validate parking session data.
        """
        # Validate that either plate or guest_plate_number is populated
        if not self.plate and not self.guest_plate_number:
            raise ValidationError(
                "Either plate or guest_plate_number must be populated"
            )
        
        # Validate status
        if self.status not in dict(self.STATUS_CHOICES):
            raise ValidationError({
                'status': f'Status must be one of: {", ".join(dict(self.STATUS_CHOICES).keys())}'
            })
        
        # Validate payment_method if provided
        if self.payment_method and self.payment_method not in dict(self.PAYMENT_METHOD_CHOICES):
            raise ValidationError({
                'payment_method': f'Payment method must be one of: {", ".join(dict(self.PAYMENT_METHOD_CHOICES).keys())}'
            })
        
        # Validate that exit_time is after entry_time if both are set
        if self.exit_time and self.entry_time and self.exit_time < self.entry_time:
            raise ValidationError({
                'exit_time': 'Exit time must be after entry time'
            })
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation.
        """
        # Run validation
        self.full_clean()
        
        super().save(*args, **kwargs)


class RateConfig(models.Model):
    """
    Admin-editable parking rate configuration.

    Only one row should be active at a time (enforced in save()).
    """

    name = models.CharField(max_length=100, default='Standard')
    rate_per_hour = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=5000,
        help_text='Hourly rate in Toman',
    )
    daily_cap = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=40000,
        help_text='Maximum charge per session in Toman',
    )
    grace_period_minutes = models.PositiveIntegerField(
        default=10,
        help_text='Free parking duration in minutes',
    )
    student_discount_percent = models.PositiveSmallIntegerField(
        default=80,
        help_text='Percent of fee charged for students (80 = 20% discount)',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this rate profile is currently in use',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rate_configs'
        verbose_name = 'Rate configuration'
        verbose_name_plural = 'Rate configurations'
        ordering = ['-is_active', '-updated_at']

    def __str__(self):
        active = ' (active)' if self.is_active else ''
        return f'{self.name}{active}'

    def save(self, *args, **kwargs):
        if self.is_active:
            RateConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(
                is_active=False
            )
        super().save(*args, **kwargs)
