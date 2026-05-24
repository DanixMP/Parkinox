"""
URL configuration for accounts app.
"""

from django.urls import path
from .views import LoginView, TokenRefreshView, OperatorLoginView
from .student_views import (
    StudentSendOtpView,
    StudentVerifyOtpView,
    StudentRegisterView,
    StudentMeView,
    StudentAddPlateView,
    StudentParkingSessionsView,
    StudentWalletTransactionsView,
)

app_name = 'accounts'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('operator-login/', OperatorLoginView.as_view(), name='operator_login'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('student/otp/send/', StudentSendOtpView.as_view(), name='student_otp_send'),
    path('student/otp/verify/', StudentVerifyOtpView.as_view(), name='student_otp_verify'),
    path('student/register/', StudentRegisterView.as_view(), name='student_register'),
    path('student/me/', StudentMeView.as_view(), name='student_me'),
    path('student/plates/add/', StudentAddPlateView.as_view(), name='student_add_plate'),
    path('student/sessions/', StudentParkingSessionsView.as_view(), name='student_sessions'),
    path('student/wallet/transactions/', StudentWalletTransactionsView.as_view(), name='student_wallet_transactions'),
]
