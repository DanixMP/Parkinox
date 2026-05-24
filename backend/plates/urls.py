"""
URL configuration for plates app.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 54.2
"""

from django.urls import path
from .views import PlateLookupView

app_name = 'plates'

urlpatterns = [
    path('lookup/', PlateLookupView.as_view(), name='plate-lookup'),
]
