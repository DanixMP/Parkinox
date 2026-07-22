"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from .health import HealthCheckView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/wallets/', include('wallets.urls')),
    path('api/plates/', include('plates.urls')),
    path('api/parking/', include('parking.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
