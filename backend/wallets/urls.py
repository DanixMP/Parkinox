from django.urls import path
from .student_views import StudentDemoTopupView
from .operator_views import OperatorTopupByPlateView

app_name = 'wallets'

urlpatterns = [
    path('student/demo-topup/', StudentDemoTopupView.as_view(), name='student_demo_topup'),
    path(
        'operator/topup-by-plate/',
        OperatorTopupByPlateView.as_view(),
        name='operator_topup_by_plate',
    ),
]
