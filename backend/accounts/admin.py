from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Admin interface for custom User model.
    """
    list_display = ('phone', 'full_name', 'student_id', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('phone', 'full_name', 'student_id', 'email')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'student_id', 'email')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'full_name', 'student_id', 'email', 'role', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('created_at', 'last_login')
    filter_horizontal = ()
