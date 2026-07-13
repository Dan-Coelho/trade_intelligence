# risk/urls.py — URLs do app de gestão de risco
#
# Tarefa 7.5.3 — Registrar URL do RiskCalculationView

from django.urls import path

from risk.views import RiskCalculationView

app_name = "risk"

urlpatterns = [
    # 7.5.2 — Cálculo de risco via HTMX (POST)
    path("calculate/", RiskCalculationView.as_view(), name="calculate"),
]
