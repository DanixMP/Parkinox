"""
WebSocket URL routing for the parking app.

This module defines the WebSocket URL patterns for real-time communication
between the operator panel and the backend.
"""

from django.urls import re_path
from parking import consumers

websocket_urlpatterns = [
    re_path(r'ws/panel/$', consumers.ParkingConsumer.as_asgi()),
]
