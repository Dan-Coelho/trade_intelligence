# dashboard/urls.py — URLs do app Dashboard

from django.urls import path
from .views import DashboardView

app_name = 'dashboard'

urlpatterns = [
    path('', DashboardView.as_view(), name='dashboard'),
]
