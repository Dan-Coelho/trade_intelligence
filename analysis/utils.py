# analysis/utils.py — Funções utilitárias do motor de análise técnica
#
# Implementações:
#   5.1.2 — calculate_atr(df): Average True Range (período 14)
#            Usado pelo motor de análise e pelo módulo de risco (Sprint 7)
#   5.2.1 — calculate_fibonacci_levels(high, low): níveis Fibonacci padrão

import logging
from decimal import Decimal

import pandas as pd

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

ATR_PERIOD = 14  # Período padrão para ATR

# Níveis de retração de Fibonacci (porcentagem do range high–low)
FIBONACCI_RATIOS = {
    '0.0%':    0.0,
    '23.6%':   0.236,
    '38.2%':   0.382,
    '50.0%':   0.500,
    '61.8%':   0.618,
    '78.6%':   0.786,
    '100.0%':  1.000,
}


# ── 5.1.2 — ATR ───────────────────────────────────────────────────────────────

def calculate_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """
    Calcula o Average True Range (ATR) de um DataFrame de OHLC.

    O ATR mede a volatilidade média de um ativo: quanto maior o ATR, mais
    volátil o ativo. É base para cálculos de stop loss e position sizing.

    Fórmula do True Range (TR):
        TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
    ATR = Média móvel exponencial do TR ao longo de `period` períodos.

    Args:
        df:     DataFrame com colunas obrigatórias: 'high', 'low', 'close'
                (case-insensitive — serão normalizadas para minúsculas).
                Deve ter pelo menos `period + 1` linhas para produzir resultado.
        period: número de períodos para a média (padrão: 14).

    Returns:
        pd.Series com o ATR calculado para cada linha. Os primeiros `period - 1`
        valores serão NaN (sem dados suficientes para a janela de cálculo).

    Raises:
        KeyError: se o DataFrame não contiver as colunas necessárias.
        ValueError: se o DataFrame estiver vazio.

    Examples:
        >>> atr_series = calculate_atr(df)
        >>> latest_atr = atr_series.dropna().iloc[-1]
    """
    if df.empty:
        raise ValueError('[calculate_atr] DataFrame está vazio.')

    # Normaliza nomes de colunas para lowercase para aceitar diferentes formatos
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    required = {'high', 'low', 'close'}
    missing  = required - set(df.columns)
    if missing:
        raise KeyError(f'[calculate_atr] Colunas ausentes no DataFrame: {missing}')

    high  = df['high'].astype(float)
    low   = df['low'].astype(float)
    close = df['close'].astype(float)

    prev_close = close.shift(1)

    # True Range: máximo entre as três medidas de volatilidade do período
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)

    # EMA do TR (Wilder's smoothing = EMA com alpha = 1/period)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    return atr


def get_latest_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> Decimal | None:
    """
    Retorna o último valor de ATR como Decimal, ou None se não houver dados suficientes.

    Wrapper conveniente para calculate_atr() utilizado pelo módulo de risco.

    Args:
        df:     DataFrame de OHLC (ver calculate_atr para formato esperado).
        period: período do ATR (padrão: 14).

    Returns:
        Decimal com o último valor de ATR, ou None.
    """
    try:
        atr_series = calculate_atr(df, period=period)
        latest = atr_series.dropna()
        if latest.empty:
            return None
        return Decimal(str(round(float(latest.iloc[-1]), 6)))
    except (KeyError, ValueError, Exception) as exc:  # noqa: BLE001
        logger.error('[get_latest_atr] Erro ao calcular ATR: %s', exc)
        return None


# ── 5.2.1 — Fibonacci ────────────────────────────────────────────────────────

def calculate_fibonacci_levels(high: float, low: float) -> dict[str, float]:
    """
    Calcula os níveis de retração de Fibonacci entre um pico (high) e um vale (low).

    Os níveis são calculados de cima para baixo (retração de uma perna de alta):
        Nível = high - (high - low) * ratio

    Ou seja, 0% = high, 100% = low (convenção de retração).

    Args:
        high: valor máximo do range (topo da perna de alta).
        low:  valor mínimo do range (fundo da perna de alta).

    Returns:
        Dict com os sete níveis Fibonacci como strings de porcentagem:
        {
            '0.0%':   <float>,   # = high
            '23.6%':  <float>,
            '38.2%':  <float>,
            '50.0%':  <float>,
            '61.8%':  <float>,
            '78.6%':  <float>,
            '100.0%': <float>,   # = low
        }

    Raises:
        ValueError: se high <= low (range inválido).

    Examples:
        >>> levels = calculate_fibonacci_levels(high=120.0, low=100.0)
        >>> levels['61.8%']
        107.64
    """
    if high <= low:
        raise ValueError(
            f'[calculate_fibonacci_levels] high ({high}) deve ser maior que low ({low}).'
        )

    price_range = high - low
    levels = {
        label: round(high - price_range * ratio, 6)
        for label, ratio in FIBONACCI_RATIOS.items()
    }

    logger.debug(
        '[calculate_fibonacci_levels] Range %.4f–%.4f → níveis: %s',
        low, high, levels,
    )
    return levels
