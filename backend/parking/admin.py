from django.contrib import admin
from .models import GateEvent, ParkingSession, RateConfig


@admin.register(GateEvent)
class GateEventAdmin(admin.ModelAdmin):
    """
    Admin interface for GateEvent model.
    Read-only to enforce immutability.
    """
    list_display = [
        'id',
        'direction',
        'camera_id',
        'plate_confirmed',
        'confidence_score',
        'was_edited',
        'was_auto_approved',
        'was_rejected',
        'operator',
        'matched_user',
        'created_at',
    ]
    list_filter = [
        'direction',
        'was_edited',
        'was_auto_approved',
        'was_rejected',
        'created_at',
    ]
    search_fields = [
        'plate_raw',
        'plate_confirmed',
        'camera_id',
        'matched_user__full_name',
        'operator__full_name',
    ]
    readonly_fields = [
        'id',
        'camera_id',
        'direction',
        'plate_raw',
        'plate_confirmed',
        'confidence_score',
        'plate_image_path',
        'was_edited',
        'was_auto_approved',
        'was_rejected',
        'operator',
        'matched_user',
        'matched_plate',
        'session',
        'created_at',
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        """Allow adding gate events through admin."""
        return True
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing gate events to enforce immutability."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deleting gate events to enforce immutability."""
        return False


@admin.register(ParkingSession)
class ParkingSessionAdmin(admin.ModelAdmin):
    """
    Admin interface for ParkingSession model.
    """
    list_display = [
        'id',
        'get_plate_display',
        'status',
        'entry_time',
        'exit_time',
        'duration_minutes',
        'fee_charged',
        'payment_method',
        'collected_by',
    ]
    list_filter = [
        'status',
        'payment_method',
        'entry_time',
    ]
    search_fields = [
        'plate__plate_number',
        'guest_plate_number',
        'plate__user__full_name',
    ]
    readonly_fields = [
        'id',
        'created_at',
        'entry_event',
        'exit_event',
    ]
    fieldsets = [
        ('Plate Information', {
            'fields': ('plate', 'guest_plate_number')
        }),
        ('Time Tracking', {
            'fields': ('entry_time', 'exit_time', 'duration_minutes')
        }),
        ('Payment Information', {
            'fields': ('fee_charged', 'status', 'payment_method', 'collected_by')
        }),
        ('Gate Events', {
            'fields': ('entry_event', 'exit_event')
        }),
        ('Additional Information', {
            'fields': ('notes', 'created_at')
        }),
    ]
    ordering = ['-entry_time']
    date_hierarchy = 'entry_time'
    
    def get_plate_display(self, obj):
        """Display plate number (registered or guest)."""
        if obj.plate:
            return f"{obj.plate.plate_number} (Registered)"
        elif obj.guest_plate_number:
            return f"{obj.guest_plate_number} (Guest)"
        return "Unknown"
    get_plate_display.short_description = 'Plate'
    get_plate_display.admin_order_field = 'plate__plate_number'


@admin.register(RateConfig)
class RateConfigAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'rate_per_hour',
        'daily_cap',
        'grace_period_minutes',
        'student_discount_percent',
        'is_active',
        'updated_at',
    ]
    list_filter = ['is_active']
    readonly_fields = ['created_at', 'updated_at']
