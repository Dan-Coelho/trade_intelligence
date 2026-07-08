# analysis/urls.py — URLs do app analysis
#
# Tarefas implementadas:
#   5.3.2 — Registra IndicatorDataView em path('indicators/', ...)

from django.urls import path

from .views import IndicatorDataView

app_name = 'analysis'

urlpatterns = [
    # 5.3.1 / 5.3.2 — Endpoint JSON de indicadores técnicos para o frontend
    # GET /analysis/indicators/?ticker=PETR4&timeframe=1d&limit=100
    path('indicators/', IndicatorDataView.as_view(), name='indicators'),
]
