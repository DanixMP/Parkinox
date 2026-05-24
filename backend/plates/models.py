from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import User
from utils.plate_normalizer import normalize_plate


class Plate(models.Model):
    """
    Registered license plate associated with a user.
    Stores Iranian vehicle license plates in normalized format.
    
    Supports:
    - National plates: [۰-۹]{2}[letter][۰-۹]{3}-[۰-۹]{2} (e.g., ۱۲ب۳۴۵-۶۷)
    - Free Zone plates: [۰-۹]{5}-[ZONE] (e.g., ۱۲۳۴۵-KISH)
    
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 52.5, 99.1
    """
    
    # Free Zone choices
    FREE_ZONE_ANZALI = 'ANZALI'
    FREE_ZONE_ARAS = 'ARAS'
    FREE_ZONE_ARVAND = 'ARVAND'
    FREE_ZONE_KISH = 'KISH'
    FREE_ZONE_MAKU = 'MAKU'
    FREE_ZONE_CHABAHAR = 'CHABAHAR'
    FREE_ZONE_QESHM = 'QESHM'
    
    FREE_ZONE_CHOICES = [
        (FREE_ZONE_ANZALI, 'Anzali Free Zone'),
        (FREE_ZONE_ARAS, 'Aras Free Zone'),
        (FREE_ZONE_ARVAND, 'Arvand Free Zone'),
        (FREE_ZONE_KISH, 'Kish Free Zone'),
        (FREE_ZONE_MAKU, 'Maku Free Zone'),
        (FREE_ZONE_CHABAHAR, 'Chabahar Free Zone'),
        (FREE_ZONE_QESHM, 'Qeshm Free Zone'),
    ]
    
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='plates',
        help_text="User who owns this plate"
    )
    plate_number = models.CharField(
        max_length=30,
        help_text="Normalized plate format: National [۰-۹]{2}[letter][۰-۹]{3}-[۰-۹]{2} or Free Zone [۰-۹]{5}-[۰-۹]{2}"
    )
    is_free_zone = models.BooleanField(
        default=False,
        help_text="Whether this is a Free Zone plate"
    )
    free_zone = models.CharField(
        max_length=20,
        choices=FREE_ZONE_CHOICES,
        null=True,
        blank=True,
        help_text="Free Zone name (only for Free Zone plates)"
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the user's primary plate"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether this plate has been verified by an operator"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this plate is currently active"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when plate was registered"
    )
    
    class Meta:
        db_table = 'plates'
        verbose_name = 'Plate'
        verbose_name_plural = 'Plates'
        unique_together = [('user', 'plate_number')]
        indexes = [
            # Index on plate_number for active plates only
            models.Index(
                fields=['plate_number'],
                condition=models.Q(is_active=True),
                name='plates_active_plate_idx'
            ),
            # Index for finding user's plates
            models.Index(fields=['user']),
            # Index for finding primary plates
            models.Index(fields=['user', 'is_primary']),
        ]
        constraints = [
            # Ensure only one primary plate per user
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(is_primary=True, is_active=True),
                name='plates_one_primary_per_user'
            ),
        ]
    
    def __str__(self):
        primary_indicator = " (اصلی)" if self.is_primary else ""
        return f"{self.plate_number}{primary_indicator} - {self.user.full_name}"
    
    def clean(self):
        """
        Validate plate number format using the plate normalizer.
        All Free Zone plates are automatically assigned to MAKU.
        """
        if self.plate_number:
            try:
                # Normalize the plate number - always use MAKU for Free Zone plates
                normalized_result = normalize_plate(
                    self.plate_number, 
                    free_zone='MAKU'  # Force MAKU for all Free Zone plates
                )
                
                # Check if it's a tuple (free zone plate) or string (national plate)
                if isinstance(normalized_result, tuple):
                    self.plate_number, detected_zone = normalized_result
                    self.is_free_zone = True
                    # Always set to MAKU
                    self.free_zone = 'MAKU'
                else:
                    self.plate_number = normalized_result
                    self.is_free_zone = False
                    self.free_zone = None
            except ValueError as e:
                raise ValidationError({'plate_number': str(e)})
    
    def save(self, *args, **kwargs):
        """
        Override save to ensure validation and handle primary plate logic.
        """
        # Run validation
        self.full_clean()
        
        # If this is the first plate for the user, make it primary
        if not self.pk and not Plate.objects.filter(user=self.user).exists():
            self.is_primary = True
        
        # If setting this plate as primary, unset other primary plates for this user
        if self.is_primary and self.is_active:
            Plate.objects.filter(
                user=self.user,
                is_primary=True,
                is_active=True
            ).exclude(pk=self.pk).update(is_primary=False)
        
        super().save(*args, **kwargs)
