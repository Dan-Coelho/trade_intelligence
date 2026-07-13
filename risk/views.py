# risk/views.py — Views do app de gestão de risco
#
# Tarefa 7.5.2 — RiskCalculationView (LoginRequiredMixin, FormView):
#   • Recebe POST com ticker + user_capital (+ opcionais win_rate, avg_win, avg_loss)
#   • Busca ATR do ativo via analysis/utils.py
#   • Calcula Kelly simplificado e position sizing
#   • Persiste em RiskCalculation
#   • Retorna partial HTML para HTMX

import logging
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic.edit import FormView
from django.http import HttpResponse
from django.template.loader import render_to_string

from analysis.utils import get_latest_atr
from market_data.models import Asset, OHLCCandle
from risk.forms import RiskForm
from risk.models import RiskCalculation

logger = logging.getLogger(__name__)

# ── Constantes de position sizing ─────────────────────────────────────────────

# Número de candles diários usados para calcular o ATR
CANDLES_FOR_ATR = 30

# Multiplicador de ATR para definir stop loss sugerido
ATR_STOP_MULTIPLIER = Decimal("2")

# Fração Kelly máxima permitida (limita alavancagem excessiva)
MAX_KELLY_FRACTION = Decimal("0.25")

# Timeframe preferencial para busca de candles
PREFERRED_TIMEFRAMES = ["1d", "1D", "daily"]


def _get_ohlc_dataframe(asset: Asset) -> pd.DataFrame | None:
    """
    Busca os candles OHLC mais recentes do ativo no banco de dados e retorna
    um DataFrame pandas com colunas high, low, close.

    Tenta timeframes em ordem de preferência. Retorna None se não houver dados.
    """
    for tf in PREFERRED_TIMEFRAMES:
        candles_qs = (
            OHLCCandle.objects
            .filter(asset=asset, timeframe=tf)
            .order_by("-timestamp")
            .values("high", "low", "close")[:CANDLES_FOR_ATR]
        )
        if candles_qs.exists():
            df = pd.DataFrame(list(candles_qs))
            df = df.iloc[::-1].reset_index(drop=True)  # ordem cronológica
            return df

    # Fallback: qualquer timeframe disponível
    candles_qs = (
        OHLCCandle.objects
        .filter(asset=asset)
        .order_by("-timestamp")
        .values("high", "low", "close")[:CANDLES_FOR_ATR]
    )
    if candles_qs.exists():
        df = pd.DataFrame(list(candles_qs))
        df = df.iloc[::-1].reset_index(drop=True)
        return df

    return None


def _calculate_kelly_fraction(
    win_rate: Decimal,
    avg_win: Decimal,
    avg_loss: Decimal,
) -> Decimal:
    """
    Calcula a fração de Kelly simplificada.

    Fórmula:
        f = (win_rate * avg_win - loss_rate * avg_loss) / avg_win

    Args:
        win_rate: taxa de acerto em percentual (ex: 55 para 55%)
        avg_win:  ganho médio por operação vencedora em R$
        avg_loss: perda média por operação perdedora em R$

    Returns:
        Fração de Kelly limitada ao intervalo [0, MAX_KELLY_FRACTION].
    """
    win_rate_dec = win_rate / Decimal("100")
    loss_rate_dec = Decimal("1") - win_rate_dec

    if avg_win <= 0:
        return Decimal("0")

    kelly = (win_rate_dec * avg_win - loss_rate_dec * avg_loss) / avg_win

    # Limita entre 0 e MAX_KELLY_FRACTION para evitar alavancagem excessiva
    kelly = max(Decimal("0"), min(kelly, MAX_KELLY_FRACTION))
    return kelly.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


class RiskCalculationView(LoginRequiredMixin, FormView):
    """
    CBV para cálculo de gestão de risco via HTMX.

    POST params (via RiskForm):
        ticker       — ticker do ativo (ex: PETR4)
        user_capital — capital disponível em R$
        win_rate     — taxa de acerto % (padrão: 55%)
        avg_win      — ganho médio R$ (padrão: 200)
        avg_loss     — perda média R$ (padrão: 100)

    Retorna:
        Partial HTML com os resultados de risco para injeção via HTMX.
    """

    form_class = RiskForm
    # Template de resultado (partial HTML injetado no #risk-result)
    template_name = "risk/partials/risk_result.html"
    # Template de erro
    error_template_name = "risk/partials/risk_error.html"

    def form_valid(self, form):
        ticker       = form.cleaned_data["ticker"]
        user_capital = form.cleaned_data["user_capital"]
        win_rate     = form.cleaned_data["win_rate"]
        avg_win      = form.cleaned_data["avg_win"]
        avg_loss     = form.cleaned_data["avg_loss"]

        # ── 1. Busca o ativo ─────────────────────────────────────────────────
        try:
            asset = Asset.objects.get(ticker=ticker)
        except Asset.DoesNotExist:
            return self._error_response(
                f'Ativo "{ticker}" não encontrado na base de dados. '
                "Busque e selecione um ativo válido no dashboard."
            )

        # ── 2. Busca ATR via analysis/utils.py ───────────────────────────────
        df = _get_ohlc_dataframe(asset)
        if df is None:
            return self._error_response(
                f'Sem dados históricos de candles para "{ticker}". '
                "Aguarde a coleta de dados ou selecione outro ativo."
            )

        atr_value = get_latest_atr(df)
        if atr_value is None:
            return self._error_response(
                f'Não foi possível calcular o ATR para "{ticker}". '
                "São necessários pelo menos 14 candles diários."
            )

        # ── 3. Calcula stop loss sugerido (ATR × 2) ──────────────────────────
        suggested_stop_loss = (atr_value * ATR_STOP_MULTIPLIER).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # ── 4. Calcula fração de Kelly simplificada ───────────────────────────
        kelly_fraction = _calculate_kelly_fraction(
            win_rate=Decimal(str(win_rate)),
            avg_win=Decimal(str(avg_win)),
            avg_loss=Decimal(str(avg_loss)),
        )

        # ── 5. Calcula position size ──────────────────────────────────────────
        # position_size = capital × kelly_fraction
        position_size = (user_capital * kelly_fraction).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Risco percentual do capital (stop loss / position size)
        risk_pct = Decimal("0")
        if position_size > 0 and suggested_stop_loss > 0:
            risk_pct = (suggested_stop_loss / position_size * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # ── 6. Persiste em RiskCalculation ───────────────────────────────────
        try:
            RiskCalculation.objects.update_or_create(
                user=self.request.user,
                asset=asset,
                defaults={
                    "atr_value":           atr_value,
                    "suggested_stop_loss": suggested_stop_loss,
                    "user_capital":        user_capital,
                    "position_size":       position_size,
                    "kelly_fraction":      kelly_fraction,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[RiskCalculationView] Falha ao persistir RiskCalculation: %s", exc)

        # ── 7. Retorna partial HTML (HTMX) ────────────────────────────────────
        context = {
            "ticker":              ticker,
            "atr_value":           atr_value,
            "suggested_stop_loss": suggested_stop_loss,
            "user_capital":        user_capital,
            "position_size":       position_size,
            "kelly_fraction":      kelly_fraction,
            "risk_pct":            risk_pct,
            "win_rate":            win_rate,
            "avg_win":             avg_win,
            "avg_loss":            avg_loss,
        }
        html = render_to_string(self.template_name, context, request=self.request)
        return HttpResponse(html)

    def form_invalid(self, form):
        # Coleta todos os erros do formulário para exibir ao usuário
        errors = []
        for field, field_errors in form.errors.items():
            for error in field_errors:
                if field == "__all__":
                    errors.append(error)
                else:
                    label = form.fields[field].label or field
                    errors.append(f"{label}: {error}")

        error_msg = " | ".join(errors) if errors else "Dados inválidos. Verifique o formulário."
        return self._error_response(error_msg)

    def _error_response(self, message: str) -> HttpResponse:
        """Retorna partial HTML de erro para injeção via HTMX."""
        html = render_to_string(
            self.error_template_name,
            {"error_message": message},
            request=self.request,
        )
        return HttpResponse(html, status=200)
