# core_app/urls.py — URLs do app core
# Tarefa 1.3.3 — Registrar URL da landing page

from django.urls import path
from .views import LandingPageView

app_name = 'core_app'

urlpatterns = [
    # 1.3.3 — Rota raiz mapeada para a LandingPageView
    path('', LandingPageView.as_view(), name='landing'),
]
