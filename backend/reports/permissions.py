"""
Custom permissions for the reports app.
Requirements: 2.5, 77.3
"""
# Re-export from shared permissions module for backward compatibility
from accounts.permissions import IsOperatorOrAdmin

__all__ = ['IsOperatorOrAdmin']
