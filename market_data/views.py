# market_data/views.py — Views do app market_data
#
# Tarefas implementadas:
#   3.4.1 — OHLCDataView: endpoint JSON de candles OHLCV para o TradingView
#   3.4.4 — AssetSearchView: busca HTMX de ticker, retorna partial HTML

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from .models import Asset, OHLCCandle


class OHLCDataView(LoginRequiredMixin, View):
    """
    Endpoint JSON que fornece candles OHLCV para o TradingView Lightweight Charts.

    Query params:
        ticker     (str, obrigatório)  — ex: 'PETR4', 'WINFUT'
        timeframe  (str, opcional)     — ex: '1m', '5m', '15m', '1h', '1D'. Padrão: '15m'
        limit      (int, opcional)     — número máximo de candles. Padrão: 300

    Resposta JSON (200):
        {
          "ticker": "PETR4",
          "asset_name": "Petróleo Brasileiro S.A.",
          "asset_type": "STOCK",
          "timeframe": "15m",
          "candles": [
            {"time": 1700000000, "open": 36.50, "high": 37.10, "low": 36.20, "close": 36.85, "volume": 123456},
            ...
          ]
        }

    Resposta JSON (400 / 404):
        {"error": "<mensagem>"}
    """

    def get(self, request, *args, **kwargs):
        ticker = request.GET.get('ticker', '').strip().upper()
        timeframe = request.GET.get('timeframe', '15m').strip()

        try:
            limit = max(1, min(int(request.GET.get('limit', 300)), 1000))
        except (ValueError, TypeError):
            limit = 300

        # ── Validações ───────────────────────────────────────────────────────
        if not ticker:
            return JsonResponse({'error': 'Parâmetro ticker é obrigatório.'}, status=400)

        try:
            asset = Asset.objects.get(ticker=ticker)
        except Asset.DoesNotExist:
            return JsonResponse(
                {'error': f'Ativo "{ticker}" não encontrado na base de dados.'},
                status=404,
            )

        # ── Consulta ─────────────────────────────────────────────────────────
        candles_qs = (
            OHLCCandle.objects
            .filter(asset=asset, timeframe=timeframe)
            .order_by('timestamp')
            .values('timestamp', 'open', 'high', 'low', 'close', 'volume')
        )

        # Aplicar limit pegando os últimos N registros
        total = candles_qs.count()
        if total > limit:
            candles_qs = candles_qs[total - limit:]

        # ── Serialização ─────────────────────────────────────────────────────
        # TradingView Lightweight Charts espera `time` como Unix timestamp (segundos UTC)
        candles = [
            {
                'time': int(c['timestamp'].timestamp()),
                'open': float(c['open']),
                'high': float(c['high']),
                'low': float(c['low']),
                'close': float(c['close']),
                'volume': c['volume'],
            }
            for c in candles_qs
        ]

        return JsonResponse({
            'ticker': asset.ticker,
            'asset_name': asset.name,
            'asset_type': asset.asset_type,
            'timeframe': timeframe,
            'candles': candles,
        })


class AssetSearchView(LoginRequiredMixin, TemplateView):
    """
    View de busca de tickers para o HTMX do header do dashboard.

    Recebe o parâmetro `q` via GET e retorna um partial HTML com as sugestões.
    Responde apenas a requisições HTMX (header HX-Request presente).

    Query params:
        q  (str) — texto de busca (ticker ou nome do ativo)

    Resposta: HTML parcial com lista de sugestões de ativos.
    """
    template_name = 'market_data/partials/asset_search_results.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '').strip()

        if len(query) >= 1:
            # Busca por ticker (prefixo) ou nome (contains), case-insensitive
            assets = (
                Asset.objects
                .filter(ticker__icontains=query)
                .order_by('ticker')[:10]
            )
            # Se não encontrou por ticker, tenta pelo nome
            if not assets.exists():
                assets = (
                    Asset.objects
                    .filter(name__icontains=query)
                    .order_by('ticker')[:10]
                )
        else:
            assets = Asset.objects.none()

        context['assets'] = assets
        context['query'] = query
        return context
