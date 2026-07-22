"""
Serializers for accounts app.
Handles user authentication and token management.
"""

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login.
    Accepts phone and password, returns JWT tokens and user info.
    
    Requirements: 1.1, 1.5, 78.1, 78.4, 79.1, 79.2
    """
    phone = serializers.CharField(required=True)
    password = serializers.CharField(required=True, write_only=True)
    
    def validate(self, attrs):
        """
        Validate credentials and authenticate user.
        """
        phone = attrs.get('phone')
        password = attrs.get('password')
        
        if not phone or not password:
            raise serializers.ValidationError('Phone and password are required.')
        
        # Authenticate user
        user = authenticate(username=phone, password=password)
        
        if user is None:
            raise serializers.ValidationError('Invalid credentials.')
        
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled.')
        
        attrs['user'] = user
        return attrs
    
    def create(self, validated_data):
        """
        Generate JWT tokens for authenticated user.
        Returns dict with access_token, refresh_token, user info, and operator_token.
        """
        user = validated_data['user']
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        
        # Generate operator_token for WebSocket authentication (same as access token for operators)
        operator_token = access_token if user.role in ['operator', 'admin'] else None
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user.id,
                'full_name': user.full_name,
                'phone': user.phone,
                'email': user.email,
                'student_id': user.student_id,
                'role': user.role,
            },
            'operator_token': operator_token,
        }


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model.
    Used for displaying user information.
    
    Requirements: 1.1, 78.1
    """
    class Meta:
        model = User
        fields = ['id', 'full_name', 'student_id', 'phone', 'email', 'role', 'is_active', 'created_at', 'last_login']
        read_only_fields = ['id', 'created_at', 'last_login']


class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for token refresh.
    Accepts refresh token and returns new access token.
    
    Requirements: 1.6, 79.3
    """
    refresh = serializers.CharField(required=True)
    
    def validate(self, attrs):
        """
        Validate refresh token.
        """
        refresh_token = attrs.get('refresh')
        
        if not refresh_token:
            raise serializers.ValidationError('Refresh token is required.')
        
        try:
            refresh = RefreshToken(refresh_token)
            attrs['refresh_obj'] = refresh
        except Exception as e:
            raise serializers.ValidationError('Invalid or expired refresh token.')
        
        return attrs
    
    def create(self, validated_data):
        """
        Generate new access token from refresh token.
        """
        refresh = validated_data['refresh_obj']
        access_token = str(refresh.access_token)
        
        return {
            'access': access_token,
            'access_token': access_token,
        }
