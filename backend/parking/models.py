import uuid

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
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

    # Stable sync identity (additive; integer PK unchanged)
    event_uuid = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        default=uuid.uuid4,
        help_text="Stable UUID for cloud sync / outbox idempotency",
    )
    
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

    # Stable sync identity (additive; integer PK unchanged)
    session_uuid = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        default=uuid.uuid4,
        help_text="Stable UUID for cloud sync / outbox idempotency",
    )
    
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


class OperationalState(models.Model):
    """Singleton operational season boundary for live dashboard counters."""

    season_started_at = models.DateTimeField(default=timezone.now)
    last_reset_at = models.DateTimeField(null=True, blank=True)
    reset_count = models.PositiveIntegerField(default=0)
    last_reset_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='season_resets',
    )

    class Meta:
        db_table = 'operational_state'
        verbose_name = 'Operational state'
        verbose_name_plural = 'Operational state'

    def __str__(self):
        return f'Season since {self.season_started_at:%Y-%m-%d %H:%M}'

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class DetectionFail(models.Model):
    """
    Operator-reviewable failed plate detection (Type A/B/C).

    Stored separately from GateEvent until an operator corrects the plate
    (then linked via gate_event) or marks the sample as not-a-plate.
    """

    FAIL_TYPE_CHOICES = [
        ('ocr_invalid_format', 'OCR invalid Iranian format'),
        ('ocr_empty', 'OCR empty / below threshold'),
        ('operator_confirmed_miss', 'Operator confirmed miss (no bbox)'),
    ]

    REVIEW_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('corrected', 'Corrected'),
        ('not_a_plate', 'Not a plate'),
        ('processed', 'Processed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    fail_type = models.CharField(max_length=32, choices=FAIL_TYPE_CHOICES)
    raw_ocr = models.CharField(max_length=64, blank=True, default='')
    validation_error = models.CharField(max_length=512, blank=True, default='')
    plate_confidence = models.DecimalField(
        max_digits=6, decimal_places=4, null=True, blank=True
    )
    char_confidence = models.DecimalField(
        max_digits=6, decimal_places=4, null=True, blank=True
    )
    bbox = models.JSONField(null=True, blank=True)
    camera_id = models.CharField(max_length=32)
    direction = models.CharField(
        max_length=10,
        choices=GateEvent.DIRECTION_CHOICES,
        default='entry',
    )
    full_image = models.ImageField(
        upload_to='detection_fails/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text='Scene A — frame at detection-fail time',
    )
    scene_b_image = models.ImageField(
        upload_to='detection_fails/%Y/%m/%d/scene_b/',
        null=True,
        blank=True,
        help_text='Scene B — delayed RTSP frame or padded bbox context',
    )
    crop_image = models.ImageField(
        upload_to='detection_fails/%Y/%m/%d/crops/',
        null=True,
        blank=True,
    )
    has_scene_b = models.BooleanField(default=False)
    scene_b_source = models.CharField(
        max_length=32,
        blank=True,
        default='',
        help_text='rtsp_delayed | padded_bbox | empty',
    )
    local_data_path = models.CharField(
        max_length=512,
        blank=True,
        default='',
        help_text='Relative path under Core/data_fails/',
    )
    review_status = models.CharField(
        max_length=20,
        choices=REVIEW_STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    not_a_plate = models.BooleanField(default=False)
    label_ground_truth = models.CharField(max_length=32, blank=True, default='')
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_detection_fails',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    gate_event = models.ForeignKey(
        GateEvent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='source_detection_fails',
    )
    sharpness = models.FloatField(null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'detection_fails'
        verbose_name = 'Detection fail'
        verbose_name_plural = 'Detection fails'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['review_status', '-created_at']),
            models.Index(fields=['fail_type', '-created_at']),
        ]

    def __str__(self):
        return f'{self.fail_type} [{self.review_status}] {self.camera_id}'


class EventMedia(models.Model):
    """Local metadata for successful entry/exit capture images (cloud-syncable)."""

    IMAGE_TYPE_CHOICES = [
        ('scene_a', 'Scene A'),
        ('scene_b', 'Scene B'),
        ('crop', 'Plate crop'),
        ('thumbnail', 'Thumbnail'),
    ]

    UPLOAD_STATUS_CHOICES = [
        ('local_only', 'Local only'),
        ('pending', 'Pending upload'),
        ('uploaded', 'Uploaded'),
        ('failed', 'Failed'),
    ]

    id = models.BigAutoField(primary_key=True)
    event_uuid = models.UUIDField(db_index=True)
    session_uuid = models.UUIDField(null=True, blank=True, db_index=True)
    gate_event = models.ForeignKey(
        GateEvent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='event_media',
    )
    image_type = models.CharField(max_length=20, choices=IMAGE_TYPE_CHOICES)
    local_path = models.CharField(max_length=1024, blank=True, default='')
    content_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    size_bytes = models.PositiveIntegerField(default=0)
    upload_status = models.CharField(
        max_length=20,
        choices=UPLOAD_STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    captured_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'event_media'
        verbose_name = 'Event media'
        verbose_name_plural = 'Event media'
        constraints = [
            models.UniqueConstraint(
                fields=['event_uuid', 'image_type'],
                name='event_media_uuid_type_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['upload_status', '-created_at']),
        ]

    def __str__(self):
        return f'{self.image_type} {self.event_uuid}'


class SyncOutbox(models.Model):
    """Durable local-first queue for cloud reporting replica push."""

    PAYLOAD_TYPE_CHOICES = [
        ('gate_event', 'Gate event'),
        ('parking_session', 'Parking session'),
        ('event_media', 'Event media'),
        ('detection_fail', 'Detection fail'),
        ('season_reset', 'Season reset'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sending', 'Sending'),
        ('acked', 'Acked'),
        ('dead_letter', 'Dead letter'),
    ]

    id = models.BigAutoField(primary_key=True)
    payload_type = models.CharField(max_length=32, choices=PAYLOAD_TYPE_CHOICES, db_index=True)
    payload_uuid = models.UUIDField(db_index=True)
    body_json = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
    )
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    acked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sync_outbox'
        verbose_name = 'Sync outbox'
        verbose_name_plural = 'Sync outbox'
        indexes = [
            models.Index(fields=['status', 'next_attempt_at', 'payload_type']),
            models.Index(fields=['payload_type', 'payload_uuid']),
        ]

    def __str__(self):
        return f'{self.payload_type}:{self.payload_uuid} [{self.status}]'


class SyncState(models.Model):
    """Singleton-ish site sync health counters."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    last_success_at = models.DateTimeField(null=True, blank=True)
    last_error_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    pending_metadata_count = models.PositiveIntegerField(default=0)
    pending_image_count = models.PositiveIntegerField(default=0)
    dead_letter_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sync_state'
        verbose_name = 'Sync state'
        verbose_name_plural = 'Sync state'

    def __str__(self):
        return f'SyncState pending_meta={self.pending_metadata_count}'

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
