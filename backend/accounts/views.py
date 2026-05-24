"""
Views for accounts app.
Handles user authentication and token management.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import LoginSerializer, TokenRefreshSerializer
from .models import User


class LoginView(APIView):
    """
    User login endpoint.
    
    POST /api/auth/login/
    Request body: {"phone": "...", "password": "..."}
    Response: {
        "access_token": "...",
        "refresh_token": "...",
        "user": {...},
        "operator_token": "..." (only for operators/admins)
    }
    
    Requirements: 1.1, 1.5, 78.1, 78.4, 78.5, 79.1, 79.2, 79.4
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Authenticate user and return JWT tokens.
        """
        serializer = LoginSerializer(data=request.data)
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_200_OK)
        
        return Response(
            {'error': 'Invalid credentials', 'details': serializer.errors},
            status=status.HTTP_401_UNAUTHORIZED
        )


class TokenRefreshView(APIView):
    """
    Token refresh endpoint.
    
    POST /api/auth/refresh/
    Request body: {"refresh": "..."}
    Response: {"access_token": "..."}
    
    Requirements: 1.6, 79.3, 79.5
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Generate new access token from refresh token.
        """
        serializer = TokenRefreshSerializer(data=request.data)
        
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_200_OK)
        
        return Response(
            {'error': 'Invalid or expired refresh token', 'details': serializer.errors},
            status=status.HTTP_401_UNAUTHORIZED
        )



class OperatorLoginView(APIView):
    """
    Operator login endpoint for desktop app.
    
    POST /api/auth/operator-login/
    Request body: {"phone": "...", "pin": "..."}
    Response: {
        "access": "...",
        "refresh": "...",
        "operator": {...}
    }
    
    Note: PIN is the same as password in the User model.
    Operators use a 4-digit PIN for quick login.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """
        Authenticate operator with phone and PIN.
        """
        phone = request.data.get('phone')
        pin = request.data.get('pin')
        
        if not phone or not pin:
            return Response(
                {'error': 'Phone and PIN are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Operator, admin, or Django superuser (by phone)
        try:
            user = User.objects.get(phone=phone)
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if user.role not in ('operator', 'admin') and not user.is_superuser:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check PIN (password)
        if not user.check_password(pin):
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if active
        if not user.is_active:
            return Response(
                {'error': 'Operator account is disabled'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Update last login
        from django.utils import timezone
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'operator': {
                'id': user.id,
                'name': user.full_name,
                'phone': user.phone,
                'role': user.role,
            }
        }, status=status.HTTP_200_OK)
