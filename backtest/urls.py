# backtest/urls.py — URLs do app backtest
#
# Tarefa 7.3.6 — Registrar URLs de backtest

from django.urls import path

from backtest.views import BacktestView, BacktestResultView, BacktestStatusView

app_name = 'backtest'

urlpatterns = [
    # GET/POST /backtest/             → formulário + disparo da task
    path('',              BacktestView.as_view(),       name='run'),

    # GET      /backtest/result/<pk>/ → página de resultado
    path('result/<int:pk>/', BacktestResultView.as_view(), name='result'),

    # GET      /backtest/status/<task_id>/ → polling Celery (JSON)
    path('status/<str:task_id>/', BacktestStatusView.as_view(), name='status'),
]
