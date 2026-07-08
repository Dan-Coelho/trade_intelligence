# analysis/views.py — Views do app analysis
#
# Tarefas implementadas:
#   5.3.1 — IndicatorDataView: endpoint JSON com últimos RSI, MACD, Bollinger
#            e ATR para o ticker/timeframe solicitado

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from market_data.models import Asset

from .models import TechnicalIndicator


class IndicatorDataView(LoginRequiredMixin, View):
    """
    Endpoint JSON que retorna os últimos valores calculados dos indicadores
    técnicos para um ativo/timeframe específico.

    Fornece dados para os sub-gráficos de RSI e MACD e para o overlay de
    Bollinger Bands no TradingView Lightweight Charts (Sprint 5.3.3 e 5.3.4).

    Query params:
        ticker     (str, obrigatório)  — ex: 'PETR4', 'WINFUT'
        timeframe  (str, opcional)     — ex: '1d', '1h', '15m'. Padrão: '1d'
        limit      (int, opcional)     — número de pontos históricos. Padrão: 100

    Resposta JSON (200):
        {
          "ticker": "PETR4",
          "timeframe": "1d",
          "rsi": [
            {"time": 1700000000, "value": 62.34},
            ...
          ],
          "macd": [
            {"time": 1700000000, "macd": 0.42, "signal": 0.31, "hist": 0.11},
            ...
          ],
          "bbands": [
            {"time": 1700000000, "upper": 37.80, "middle": 36.50, "lower": 35.20},
            ...
          ],
          "atr": [
            {"time": 1700000000, "value": 0.85},
            ...
          ],
          "latest": {
            "rsi": 62.34,
            "macd": 0.42,
            "macd_signal": 0.31,
            "macd_hist": 0.11,
            "bb_upper": 37.80,
            "bb_middle": 36.50,
            "bb_lower": 35.20,
            "atr": 0.85
          }
        }

    Resposta JSON (400 / 404):
        {"error": "<mensagem>"}
    """

    def get(self, request, *args, **kwargs):
        ticker    = request.GET.get('ticker', '').strip().upper()
        timeframe = request.GET.get('timeframe', '1d').strip()

        try:
            limit = max(1, min(int(request.GET.get('limit', 100)), 500))
        except (ValueError, TypeError):
            limit = 100

        # ── Validações ────────────────────────────────────────────────────────
        if not ticker:
            return JsonResponse(
                {'error': 'Parâmetro ticker é obrigatório.'}, status=400
            )

        try:
            asset = Asset.objects.get(ticker=ticker)
        except Asset.DoesNotExist:
            return JsonResponse(
                {'error': f'Ativo "{ticker}" não encontrado na base de dados.'},
                status=404,
            )

        # ── Busca dos indicadores ─────────────────────────────────────────────
        def _get_series(indicator_name: str) -> list:
            """Busca a série histórica de um indicador, ordenada por timestamp."""
            qs = (
                TechnicalIndicator.objects
                .filter(asset=asset, indicator_name=indicator_name, timeframe=timeframe)
                .order_by('timestamp')
                .values('timestamp', 'values')
            )
            # Aplica limit pegando os últimos N registros
            total = qs.count()
            if total > limit:
                qs = qs[total - limit:]
            return list(qs)

        rsi_qs    = _get_series('RSI')
        macd_qs   = _get_series('MACD')
        bbands_qs = _get_series('BBANDS')
        atr_qs    = _get_series('ATR')

        # ── Serialização — RSI ────────────────────────────────────────────────
        # Formato: [{time, value}]
        rsi_series = [
            {
                'time':  int(row['timestamp'].timestamp()),
                'value': row['values'].get('rsi'),
            }
            for row in rsi_qs
            if row['values'].get('rsi') is not None
        ]

        # ── Serialização — MACD ───────────────────────────────────────────────
        # Formato: [{time, macd, signal, hist}]
        macd_series = [
            {
                'time':   int(row['timestamp'].timestamp()),
                'macd':   row['values'].get('macd'),
                'signal': row['values'].get('signal'),
                'hist':   row['values'].get('hist'),
            }
            for row in macd_qs
            if row['values'].get('macd') is not None
        ]

        # ── Serialização — Bollinger Bands ────────────────────────────────────
        # Formato: [{time, upper, middle, lower, bandwidth, percent_b}]
        bbands_series = [
            {
                'time':       int(row['timestamp'].timestamp()),
                'upper':      row['values'].get('upper'),
                'middle':     row['values'].get('middle'),
                'lower':      row['values'].get('lower'),
                'bandwidth':  row['values'].get('bandwidth'),
                'percent_b':  row['values'].get('percent_b'),
            }
            for row in bbands_qs
            if row['values'].get('upper') is not None
        ]

        # ── Serialização — ATR ────────────────────────────────────────────────
        atr_series = [
            {
                'time':  int(row['timestamp'].timestamp()),
                'value': row['values'].get('atr'),
            }
            for row in atr_qs
            if row['values'].get('atr') is not None
        ]

        # ── Snapshot dos últimos valores ──────────────────────────────────────
        latest = {
            'rsi':         rsi_series[-1]['value']         if rsi_series    else None,
            'macd':        macd_series[-1]['macd']         if macd_series   else None,
            'macd_signal': macd_series[-1]['signal']       if macd_series   else None,
            'macd_hist':   macd_series[-1]['hist']         if macd_series   else None,
            'bb_upper':    bbands_series[-1]['upper']      if bbands_series else None,
            'bb_middle':   bbands_series[-1]['middle']     if bbands_series else None,
            'bb_lower':    bbands_series[-1]['lower']      if bbands_series else None,
            'atr':         atr_series[-1]['value']         if atr_series    else None,
        }

        return JsonResponse({
            'ticker':    asset.ticker,
            'timeframe': timeframe,
            'rsi':       rsi_series,
            'macd':      macd_series,
            'bbands':    bbands_series,
            'atr':       atr_series,
            'latest':    latest,
        })
