from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.overview, name='overview'),
    path('parked/', views.parked, name='parked'),
    path('history/', views.history, name='history'),
    path('sessions/<uuid:session_uuid>/', views.session_detail, name='session_detail'),
    path('sessions/<uuid:session_uuid>/images.zip', views.session_images_zip, name='session_images_zip'),
    path('search/', views.search, name='search'),
    path('fails/', views.fails, name='fails'),
    path('sync/', views.sync_health, name='sync'),
    path('sync/requeue/', views.requeue_media, name='sync_requeue'),
    path('reports/', views.reports_page, name='reports'),
    path('reports/excel/', views.export_excel, name='export_excel'),
    path('reports/pdf/', views.export_pdf, name='export_pdf'),
    path('reports/csv/', views.export_csv, name='export_csv'),
    path('analytics/', views.analytics, name='analytics'),
    path('season/reset/', views.season_reset, name='season_reset'),
    path('files/<int:media_id>/', views.media_file, name='media_file'),
]
