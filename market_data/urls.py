# market_data/urls.py — Rotas do app market_data
#
# Tarefas implementadas:
#   3.4.2 — path('ohlc-data/') → OHLCDataView
#   3.4.4 — path('search/') → AssetSearchView (busca HTMX)

from django.urls import path

from .views import AssetSearchView, OHLCDataView

app_name = 'market_data'

urlpatterns = [
    # 3.4.2 — Endpoint JSON de candles OHLCV para o TradingView
    # Uso: GET /market-data/ohlc-data/?ticker=PETR4&timeframe=15m
    path('ohlc-data/', OHLCDataView.as_view(), name='ohlc_data'),

    # 3.4.4 — Busca HTMX de ticker — retorna partial HTML de sugestões
    # Uso: GET /market-data/search/?q=PETR
    path('search/', AssetSearchView.as_view(), name='asset_search'),
]
