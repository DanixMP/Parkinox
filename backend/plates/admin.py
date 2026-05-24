from django.contrib import admin
from .models import Plate


@admin.register(Plate)
class PlateAdmin(admin.ModelAdmin):
    """
    Admin interface for Plate model.
    """
    list_display = [
        'plate_number',
        'user',
        'is_free_zone',
        'free_zone',
        'is_primary',
        'is_verified',
        'is_active',
        'created_at'
    ]
    list_filter = [
        'is_free_zone',
        'free_zone',
        'is_primary',
        'is_verified',
        'is_active',
        'created_at'
    ]
    search_fields = [
        'plate_number',
        'user__full_name',
        'user__phone',
        'user__student_id',
        'free_zone'
    ]
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Plate Information', {
            'fields': ('user', 'plate_number', 'is_free_zone', 'free_zone')
        }),
        ('Status', {
            'fields': ('is_primary', 'is_verified', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
