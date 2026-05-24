"""
Custom JWT authentication that validates user is active.
Requirements: 76.1, 76.2, 76.3, 76.4, 76.5
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class ActiveUserJWTAuthentication(JWTAuthentication):
    """
    Extends JWTAuthentication to also verify the user account is active.
    Returns 401 for invalid/expired tokens and inactive users.
    Requirements: 76.4, 76.5
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not user.is_active:
            raise AuthenticationFailed(
                'User account is inactive.',
                code='user_inactive',
            )
        return user
