"""
Serializers for the plates app.

Requirements: 8.1, 8.2, 8.3, 8.4
"""

from rest_framework import serializers
from .models import Plate
from accounts.models import User
from wallets.models import Wallet


class PlateLookupSerializer(serializers.Serializer):
    """
    Serializer for plate lookup response.
    
    Returns user information, wallet balance, and active session status
    for a registered plate.
    
    Requirements: 8.1, 8.2, 8.3
    """
    # Plate information
    plate_number = serializers.CharField(
        help_text="Normalized plate number"
    )
    is_registered = serializers.BooleanField(
        help_text="Whether the plate is registered in the system"
    )
    is_free_zone = serializers.BooleanField(
        default=False,
        help_text="Whether this is a Free Zone plate"
    )
    free_zone = serializers.CharField(
        allow_null=True,
        required=False,
        help_text="Free Zone name (e.g., KISH, QESHM, ANZALI)"
    )
    
    # User information (null if not registered)
    user_id = serializers.IntegerField(
        allow_null=True,
        help_text="User ID associated with the plate"
    )
    user_name = serializers.CharField(
        allow_null=True,
        help_text="Full name of the user"
    )
    student_id = serializers.CharField(
        allow_null=True,
        help_text="Student ID if user is a student"
    )
    user_role = serializers.CharField(
        allow_null=True,
        help_text="User role: student, operator, or admin"
    )
    
    # Wallet information (null if not registered)
    wallet_balance = serializers.IntegerField(
        allow_null=True,
        help_text="Current wallet balance in Toman"
    )
    
    # Active session information (null if no active session)
    has_active_session = serializers.BooleanField(
        help_text="Whether the plate has an active parking session"
    )
    active_session_id = serializers.IntegerField(
        allow_null=True,
        help_text="ID of the active parking session if exists"
    )
    active_session_entry_time = serializers.DateTimeField(
        allow_null=True,
        help_text="Entry time of the active session"
    )
