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

    # Operational season
    path('season/reset/', views.reset_season, name='reset_season'),

    # Detection fail capture / operator review
    path(
        'detection-fails/ingest/',
        views.ingest_detection_fail,
        name='ingest_detection_fail',
    ),
    path(
        'detection-fails/metrics/',
        views.detection_fail_metrics,
        name='detection_fail_metrics',
    ),
    path(
        'detection-fails/',
        views.list_detection_fails,
        name='list_detection_fails',
    ),
    path(
        'detection-fails/<uuid:fail_id>/',
        views.get_detection_fail,
        name='get_detection_fail',
    ),
    path(
        'detection-fails/<uuid:fail_id>/review/',
        views.review_detection_fail,
        name='review_detection_fail',
    ),

    # Cloud sync health (local outbox)
    path('sync/status/', views.sync_status, name='sync_status'),
    path('sync/requeue/', views.sync_requeue, name='sync_requeue'),
]
