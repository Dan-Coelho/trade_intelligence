# analysis/tasks.py — Tasks Celery do motor de análise técnica
#
# Implementações:
#   5.1.1 — run_technical_analysis(asset_id): busca os últimos N candles, calcula
#            RSI (14), MACD (12,26,9), Bollinger Bands (20, 2) com pandas puro e
#            persiste em TechnicalIndicator
#   5.1.3 — detect_candlestick_patterns(asset_id): detecta padrões de candle
#            com pandas puro e persiste em CandlestickPattern
#
# Dependências: apenas pandas (já instalado via yfinance). Sem pandas-ta ou TA-Lib.

import logging
from datetime import timezone

import pandas as pd
from celery import shared_task

from market_data.models import Asset, OHLCCandle

from .models import CandlestickPattern, TechnicalIndicator

logger = logging.getLogger(__name__)


# ── Constantes ────────────────────────────────────────────────────────────────

CANDLES_LOOKBACK = 200  # Candles buscados (garante janela estável p/ MACD de 26)

RSI_PERIOD    = 14
MACD_FAST     = 12
MACD_SLOW     = 26
MACD_SIGNAL   = 9
BBANDS_PERIOD = 20
BBANDS_STD    = 2.0
ATR_PERIOD    = 14


# ── Helpers — DataFrame ───────────────────────────────────────────────────────

def _get_candles_df(asset: Asset, timeframe: str, n: int = CANDLES_LOOKBACK) -> pd.DataFrame:
    """
    Busca os últimos N candles de um ativo/timeframe como DataFrame pandas.

    Colunas: open, high, low, close, volume. Index: timestamp (DatetimeIndex, UTC).
    """
    qs = (
        OHLCCandle.objects
        .filter(asset=asset, timeframe=timeframe)
        .order_by('-timestamp')[:n]
    )
    if not qs:
        return pd.DataFrame()

    records = [
        {
            'timestamp': c.timestamp,
            'open':   float(c.open),
            'high':   float(c.high),
            'low':    float(c.low),
            'close':  float(c.close),
            'volume': float(c.volume),
        }
        for c in qs
    ]

    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df = df.set_index('timestamp')
    return df


def _f(value) -> float | None:
    """Converte para float arredondado ou None se NaN."""
    try:
        v = float(value)
        return None if pd.isna(v) else round(v, 6)
    except (TypeError, ValueError):
        return None


def _last_ts(df: pd.DataFrame):
    """Extrai último timestamp do DataFrame como datetime com UTC."""
    ts = df.index[-1]
    if hasattr(ts, 'to_pydatetime'):
        ts = ts.to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


# ── Cálculos de indicadores (pandas puro) ─────────────────────────────────────

def _calc_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """
    RSI — Relative Strength Index.

    Usa a suavização exponencial de Wilder (EMA com alpha = 1/period).
    Valores: 0–100. Sobrecomprado > 70, sobrevendido < 30.
    """
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs    = gain / loss.replace(0, float('nan'))
    return 100 - (100 / (1 + rs))


def _calc_macd(
    close: pd.Series,
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    MACD — Moving Average Convergence Divergence.

    Retorna: (macd_line, signal_line, histogram)
    """
    ema_fast   = close.ewm(span=fast,   adjust=False).mean()
    ema_slow   = close.ewm(span=slow,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def _calc_bbands(
    close: pd.Series,
    period: int = BBANDS_PERIOD,
    std_mult: float = BBANDS_STD,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands.

    Retorna: (upper, middle, lower, bandwidth, percent_b)
    """
    middle    = close.rolling(period).mean()
    std       = close.rolling(period).std(ddof=0)
    upper     = middle + std_mult * std
    lower     = middle - std_mult * std
    bandwidth = (upper - lower) / middle.replace(0, float('nan'))
    pct_b     = (close - lower) / (upper - lower).replace(0, float('nan'))
    return upper, middle, lower, bandwidth, pct_b


def _calc_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = ATR_PERIOD,
) -> pd.Series:
    """
    ATR — Average True Range (Wilder's EMA).

    True Range = max(H-L, |H-C_prev|, |L-C_prev|)
    """
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


# ── Task 5.1.1 — run_technical_analysis ──────────────────────────────────────

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=30,
    name='analysis.tasks.run_technical_analysis',
)
def run_technical_analysis(self, asset_id: int, timeframe: str = '1d') -> dict:
    """
    Calcula RSI, MACD, Bollinger Bands e ATR para um ativo e persiste em TechnicalIndicator.

    Implementação com pandas puro — sem dependência de pandas-ta ou TA-Lib.

    Indicadores calculados:
        - RSI  (período 14): momentum oscillator 0–100
        - MACD (12,26,9): trend/momentum (line, signal, histogram)
        - Bollinger Bands (20, 2σ): upper, middle, lower, bandwidth, %B
        - ATR  (período 14): volatilidade média — usado pelo módulo de risco

    Upsert por (asset, indicator_name, timeframe, timestamp).
    Ao final, dispara detect_candlestick_patterns.delay() para o mesmo ativo.

    Args:
        asset_id:  ID do Asset a processar.
        timeframe: timeframe dos candles (padrão: '1d').

    Returns:
        Dict com indicadores calculados e seus valores mais recentes.
    """
    try:
        asset = Asset.objects.get(pk=asset_id)
    except Asset.DoesNotExist:
        logger.error('[run_technical_analysis] Asset id=%d não encontrado.', asset_id)
        return {'error': f'Asset {asset_id} not found'}

    df = _get_candles_df(asset, timeframe)

    if len(df) < MACD_SLOW + 1:
        logger.warning(
            '[run_technical_analysis] %s/%s: apenas %d candles (mín. %d). Aguardando.',
            asset.ticker, timeframe, len(df), MACD_SLOW + 1,
        )
        return {'status': 'insufficient_data', 'candles': len(df)}

    close = df['close']
    high  = df['high']
    low   = df['low']
    ts    = _last_ts(df)

    # ── Cálculos ──────────────────────────────────────────────────────────────
    rsi = _calc_rsi(close)
    macd_line, signal_line, histogram = _calc_macd(close)
    bb_upper, bb_mid, bb_lower, bb_bw, bb_pct = _calc_bbands(close)
    atr = _calc_atr(high, low, close)

    rsi_val       = _f(rsi.iloc[-1])
    macd_val      = _f(macd_line.iloc[-1])
    signal_val    = _f(signal_line.iloc[-1])
    hist_val      = _f(histogram.iloc[-1])
    bb_upper_val  = _f(bb_upper.iloc[-1])
    bb_mid_val    = _f(bb_mid.iloc[-1])
    bb_lower_val  = _f(bb_lower.iloc[-1])
    bb_bw_val     = _f(bb_bw.iloc[-1])
    bb_pct_val    = _f(bb_pct.iloc[-1])
    atr_val       = _f(atr.iloc[-1])

    # ── Persistência ──────────────────────────────────────────────────────────
    saved = []

    def _upsert(name: str, values: dict) -> None:
        clean = {k: v for k, v in values.items() if v is not None}
        if not clean:
            return
        TechnicalIndicator.objects.update_or_create(
            asset=asset,
            indicator_name=name,
            timeframe=timeframe,
            timestamp=ts,
            defaults={'values': clean},
        )
        saved.append(name)

    _upsert('RSI', {
        'rsi':    rsi_val,
        'period': RSI_PERIOD,
    })

    _upsert('MACD', {
        'macd':          macd_val,
        'signal':        signal_val,
        'hist':          hist_val,
        'fast':          MACD_FAST,
        'slow':          MACD_SLOW,
        'signal_period': MACD_SIGNAL,
    })

    _upsert('BBANDS', {
        'upper':     bb_upper_val,
        'middle':    bb_mid_val,
        'lower':     bb_lower_val,
        'bandwidth': bb_bw_val,
        'percent_b': bb_pct_val,
        'period':    BBANDS_PERIOD,
        'std':       BBANDS_STD,
    })

    _upsert('ATR', {
        'atr':    atr_val,
        'period': ATR_PERIOD,
    })

    logger.info(
        '[run_technical_analysis] %s/%s → %s | RSI=%.2f | MACD=%.4f | ATR=%.4f',
        asset.ticker, timeframe, saved,
        rsi_val or 0, macd_val or 0, atr_val or 0,
    )

    # Dispara detecção de padrões de forma assíncrona
    detect_candlestick_patterns.delay(asset_id, timeframe)

    return {
        'status':    'ok',
        'asset':     asset.ticker,
        'timeframe': timeframe,
        'indicators': saved,
        'rsi':       rsi_val,
        'macd':      macd_val,
        'bb_upper':  bb_upper_val,
        'bb_lower':  bb_lower_val,
        'atr':       atr_val,
    }


# ── Detecção de padrões (pandas puro) ────────────────────────────────────────

def _body(df: pd.DataFrame) -> pd.Series:
    return (df['close'] - df['open']).abs()

def _upper_shadow(df: pd.DataFrame) -> pd.Series:
    return df['high'] - df[['open', 'close']].max(axis=1)

def _lower_shadow(df: pd.DataFrame) -> pd.Series:
    return df[['open', 'close']].min(axis=1) - df['low']

def _range(df: pd.DataFrame) -> pd.Series:
    return (df['high'] - df['low']).replace(0, float('nan'))

def _is_bullish(df: pd.DataFrame) -> pd.Series:
    return df['close'] > df['open']

def _is_bearish(df: pd.DataFrame) -> pd.Series:
    return df['close'] < df['open']


def _detect_all_patterns(df: pd.DataFrame) -> list[dict]:
    """
    Detecta padrões de candle no último candle do DataFrame via pandas puro.

    Implementa os padrões mais relevantes para o mercado intraday:
        Doji, Hammer, Inverted Hammer, Shooting Star, Bullish/Bearish Engulfing,
        Bullish/Bearish Marubozu, Spinning Top, Bullish/Bearish Harami,
        Morning Star, Evening Star.

    Returns:
        Lista de dicts {'pattern': str, 'direction': str} para cada padrão detectado
        no último candle.
    """
    if len(df) < 3:
        return []

    found = []
    D = CandlestickPattern.Direction

    body     = _body(df)
    up_sh    = _upper_shadow(df)
    low_sh   = _lower_shadow(df)
    rng      = _range(df)
    bull     = _is_bullish(df)
    bear     = _is_bearish(df)

    # Índices dos últimos 3 candles
    i  = -1   # atual
    i1 = -2   # anterior
    i2 = -3   # ante-anterior

    body_ratio = body / rng
    eps        = rng * 0.05  # 5% do range como tolerância

    def add(pattern_name: str, direction: str) -> None:
        found.append({'pattern': pattern_name, 'direction': direction})

    # ── Doji ─────────────────────────────────────────────────────────────────
    # Corpo < 10% do range total
    if body_ratio.iloc[i] < 0.10:
        add('Doji', D.NEUTRAL)

    # ── Hammer ───────────────────────────────────────────────────────────────
    # Sombra inferior > 2x corpo, sombra superior < corpo, corpo pequeno-médio
    if (
        low_sh.iloc[i] > 2 * body.iloc[i]
        and up_sh.iloc[i] < body.iloc[i]
        and body_ratio.iloc[i] > 0.05
    ):
        add('Hammer', D.BULLISH)

    # ── Inverted Hammer ───────────────────────────────────────────────────────
    if (
        up_sh.iloc[i] > 2 * body.iloc[i]
        and low_sh.iloc[i] < body.iloc[i]
        and body_ratio.iloc[i] > 0.05
    ):
        add('Inverted Hammer', D.BULLISH)

    # ── Shooting Star ─────────────────────────────────────────────────────────
    # Igual ao Inverted Hammer, mas em tendência de alta e bearish
    if (
        bear.iloc[i]
        and up_sh.iloc[i] > 2 * body.iloc[i]
        and low_sh.iloc[i] < body.iloc[i]
    ):
        add('Shooting Star', D.BEARISH)

    # ── Bullish Engulfing ─────────────────────────────────────────────────────
    # Candle atual bullish cobre completamente o corpo do anterior (bearish)
    if (
        bull.iloc[i]
        and bear.iloc[i1]
        and df['open'].iloc[i]  <= df['close'].iloc[i1]
        and df['close'].iloc[i] >= df['open'].iloc[i1]
    ):
        add('Bullish Engulfing', D.BULLISH)

    # ── Bearish Engulfing ─────────────────────────────────────────────────────
    if (
        bear.iloc[i]
        and bull.iloc[i1]
        and df['open'].iloc[i]  >= df['close'].iloc[i1]
        and df['close'].iloc[i] <= df['open'].iloc[i1]
    ):
        add('Bearish Engulfing', D.BEARISH)

    # ── Bullish Harami ────────────────────────────────────────────────────────
    # Corpo atual está dentro do corpo anterior (bearish grande)
    if (
        bull.iloc[i]
        and bear.iloc[i1]
        and df['open'].iloc[i]  > df['close'].iloc[i1]
        and df['close'].iloc[i] < df['open'].iloc[i1]
    ):
        add('Bullish Harami', D.BULLISH)

    # ── Bearish Harami ────────────────────────────────────────────────────────
    if (
        bear.iloc[i]
        and bull.iloc[i1]
        and df['open'].iloc[i]  < df['close'].iloc[i1]
        and df['close'].iloc[i] > df['open'].iloc[i1]
    ):
        add('Bearish Harami', D.BEARISH)

    # ── Bullish Marubozu ──────────────────────────────────────────────────────
    # Corpo ocupa > 95% do range, bullish
    if bull.iloc[i] and body_ratio.iloc[i] > 0.95:
        add('Bullish Marubozu', D.BULLISH)

    # ── Bearish Marubozu ──────────────────────────────────────────────────────
    if bear.iloc[i] and body_ratio.iloc[i] > 0.95:
        add('Bearish Marubozu', D.BEARISH)

    # ── Spinning Top ──────────────────────────────────────────────────────────
    # Corpo pequeno (15–40%), sombras significativas dos dois lados
    if (
        0.10 < body_ratio.iloc[i] < 0.40
        and up_sh.iloc[i] > body.iloc[i] * 0.5
        and low_sh.iloc[i] > body.iloc[i] * 0.5
    ):
        add('Spinning Top', D.NEUTRAL)

    # ── Morning Star (3 candles) ──────────────────────────────────────────────
    # 1: bearish grande | 2: doji/corpo pequeno | 3: bullish grande
    if len(df) >= 3:
        c1_big_bear  = bear.iloc[i2] and body_ratio.iloc[i2] > 0.60
        c2_small     = body_ratio.iloc[i1] < 0.20
        c3_big_bull  = bull.iloc[i]  and body_ratio.iloc[i]  > 0.50
        # Fechamento do candle 3 entra no corpo do candle 1
        c3_recovers  = df['close'].iloc[i] > (df['open'].iloc[i2] + df['close'].iloc[i2]) / 2
        if c1_big_bear and c2_small and c3_big_bull and c3_recovers:
            add('Morning Star', D.BULLISH)

    # ── Evening Star (3 candles) ──────────────────────────────────────────────
    if len(df) >= 3:
        c1_big_bull  = bull.iloc[i2] and body_ratio.iloc[i2] > 0.60
        c2_small     = body_ratio.iloc[i1] < 0.20
        c3_big_bear  = bear.iloc[i]  and body_ratio.iloc[i]  > 0.50
        c3_drops     = df['close'].iloc[i] < (df['open'].iloc[i2] + df['close'].iloc[i2]) / 2
        if c1_big_bull and c2_small and c3_big_bear and c3_drops:
            add('Evening Star', D.BEARISH)

    return found


# ── Task 5.1.3 — detect_candlestick_patterns ─────────────────────────────────

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=30,
    name='analysis.tasks.detect_candlestick_patterns',
)
def detect_candlestick_patterns(self, asset_id: int, timeframe: str = '1d') -> dict:
    """
    Detecta padrões de candlestick com pandas puro e persiste em CandlestickPattern.

    Padrões detectados:
        Doji, Hammer, Inverted Hammer, Shooting Star,
        Bullish/Bearish Engulfing, Bullish/Bearish Harami,
        Bullish/Bearish Marubozu, Spinning Top,
        Morning Star, Evening Star.

    Upsert por (asset, pattern_name, timeframe, timestamp).

    Args:
        asset_id:  ID do Asset a processar.
        timeframe: timeframe dos candles (padrão: '1d').

    Returns:
        Dict com padrões detectados.
    """
    try:
        asset = Asset.objects.get(pk=asset_id)
    except Asset.DoesNotExist:
        logger.error('[detect_candlestick_patterns] Asset id=%d não encontrado.', asset_id)
        return {'error': f'Asset {asset_id} not found'}

    df = _get_candles_df(asset, timeframe, n=50)

    if len(df) < 3:
        logger.warning(
            '[detect_candlestick_patterns] %s/%s: apenas %d candles (mín. 3).',
            asset.ticker, timeframe, len(df),
        )
        return {'status': 'insufficient_data', 'candles': len(df)}

    ts      = _last_ts(df)
    patterns = _detect_all_patterns(df)

    for p in patterns:
        CandlestickPattern.objects.update_or_create(
            asset=asset,
            pattern_name=p['pattern'],
            timeframe=timeframe,
            timestamp=ts,
            defaults={
                'direction':  p['direction'],
                'confidence': 100.00,
            },
        )

    logger.info(
        '[detect_candlestick_patterns] %s/%s: %d padrão(ões): %s',
        asset.ticker, timeframe, len(patterns),
        [p['pattern'] for p in patterns],
    )

    return {
        'status':            'ok',
        'asset':             asset.ticker,
        'timeframe':         timeframe,
        'patterns_detected': len(patterns),
        'patterns':          patterns,
    }
