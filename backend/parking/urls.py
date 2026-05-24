"""
URL configuration for parking app.
"""

from django.urls import path
from . import views

app_name = 'parking'

urlpatterns = [
    path('rates/', views.rate_config, name='rate_config'),
    # Gate events
    path('gate-events/', views.create_gate_event, name='create_gate_event'),
    
    # Plate lookup (check if plate is registered)
    path('plates/lookup/', views.lookup_plate, name='lookup_plate'),
    
    # Parking sessions
    path('sessions/', views.get_parked_vehicles, name='get_parked_vehicles'),
    path('sessions/<int:session_id>/', views.get_session, name='get_session'),
    path('sessions/<int:session_id>/cash-payment/', views.record_cash_payment, name='record_cash_payment'),
    path('sessions/<int:session_id>/waive-fee/', views.waive_fee, name='waive_fee'),
]
