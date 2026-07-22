from django.urls import path

from . import views

urlpatterns = [
    path('health/', views.health, name='ingest_health'),
    path('events/', views.ingest_events, name='ingest_events'),
    path('images/', views.ingest_images, name='ingest_images'),
    path('reconcile/', views.reconcile, name='ingest_reconcile'),
]
