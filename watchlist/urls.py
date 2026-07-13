# watchlist/urls.py — URLs do app watchlist
#
# Tarefa 7.4.7 — Registrar todas as URLs de watchlist e alertas

from django.urls import path

from watchlist.views import (
    AlertCreateView,
    AlertDeleteView,
    AlertListView,
    WatchlistAddView,
    WatchlistRemoveView,
)

app_name = 'watchlist'

urlpatterns = [
    # 7.4.2 — Adicionar ativo à watchlist (HTMX POST)
    path('add/',                   WatchlistAddView.as_view(),    name='add'),

    # 7.4.3 — Remover ativo da watchlist (HTMX POST)
    path('remove/<int:asset_id>/', WatchlistRemoveView.as_view(), name='remove'),

    # 7.4.4 — Criar alerta de preço
    path('alerts/add/',            AlertCreateView.as_view(),     name='alert_create'),

    # Lista de alertas do usuário
    path('alerts/',                AlertListView.as_view(),       name='alert_list'),

    # Excluir alerta
    path('alerts/<int:pk>/delete/', AlertDeleteView.as_view(),    name='alert_delete'),
]
