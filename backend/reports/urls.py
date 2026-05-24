from django.urls import path
from .views import (
    DailySummaryView,
    DailySessionsView,
    ExcelReportView,
    PDFReportView,
)

app_name = 'reports'

urlpatterns = [
    path('daily/', DailySummaryView.as_view(), name='daily-summary'),
    path('daily/sessions/', DailySessionsView.as_view(), name='daily-sessions'),
    path('export/excel/', ExcelReportView.as_view(), name='export-excel'),
    path('export/pdf/', PDFReportView.as_view(), name='export-pdf'),
]
