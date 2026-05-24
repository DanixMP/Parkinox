"""
Role-based permission classes for the Parkinox system.
Requirements: 2.3, 2.4, 2.5, 77.1, 77.2, 77.3, 77.4, 77.5
"""
from rest_framework.permissions import BasePermission


class IsOperatorOrAdmin(BasePermission):
    """
    Allows access only to users with 'operator' or 'admin' roles.
    Requirements: 2.3, 2.4, 2.5, 77.1, 77.2, 77.3
    """
    message = 'Access restricted to operators and admins.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('operator', 'admin')
        )


class IsAdminUser(BasePermission):
    """
    Allows access only to users with 'admin' role.
    Requirements: 77.4
    """
    message = 'Access restricted to admins only.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
        )


class IsOperator(BasePermission):
    """
    Allows access to users with 'operator' or 'admin' role.
    Admins have full operator access.
    """
    message = 'Access restricted to operators and admins.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ('operator', 'admin')
        )


class IsOwnerOrOperatorOrAdmin(BasePermission):
    """
    Allows students to access only their own data.
    Operators and admins can access any data.
    Requirements: 77.4, 77.5
    """
    message = 'You do not have permission to access this resource.'

    def has_object_permission(self, request, view, obj):
        if request.user.role in ('operator', 'admin'):
            return True
        # Students can only access their own data
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'id'):
            return obj == request.user
        return False
