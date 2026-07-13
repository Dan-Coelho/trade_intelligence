# backtest/tasks.py — Task Celery de execução de backtest
#
# Tarefa 7.3.3 — run_backtest(user_id, ticker, start_date, end_date, strategy, capital):
#   Busca OHLC do banco, executa o backtest com pandas puro e persiste em BacktestResult.

import logging
import math
from datetime import date, datetime, timezone

import pandas as pd
from celery import shared_task

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

RISK_FREE_RATE = 0.1075  # Taxa livre de risco anualizada (SELIC aproximada)
TRADING_DAYS   = 252


# ─────────────────────────────────────────────────────────────────────────────
# 7.3.3 — Task principal
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2,
    default_retry_delay=30,
    name='backtest.tasks.run_backtest',
)
def run_backtest(
    self,
    user_id:    int,
    ticker:     str,
    start_date: str,   # ISO format: 'YYYY-MM-DD'
    end_date:   str,
    strategy:   str,
    capital:    float,
) -> dict:
    """
    Executa backtest de estratégia sobre dados OHLC históricos do banco.

    Fluxo:
        1. Carrega candles diários do banco para o período.
        2. Aplica a estratégia escolhida (SMA, RSI, MACD, Bollinger, B&H).
        3. Simula trades e calcula métricas: Win Rate, Sharpe, Max Drawdown.
        4. Persiste resultado em BacktestResult.

    Args:
        user_id:    PK do usuário que disparou o backtest.
        ticker:     Código do ativo (ex.: 'PETR4').
        start_date: Data de início ISO (ex.: '2024-01-01').
        end_date:   Data de fim ISO (ex.: '2024-12-31').
        strategy:   Chave da estratégia (ex.: 'sma_crossover').
        capital:    Capital inicial em R$.

    Returns:
        Dict com id do BacktestResult criado e métricas principais.
    """
    from django.contrib.auth import get_user_model  # noqa: PLC0415
    from market_data.models import Asset, OHLCCandle  # noqa: PLC0415
    from backtest.models import BacktestResult        # noqa: PLC0415

    User = get_user_model()

    # ── 1. Buscar usuário e asset ──────────────────────────────────────────────
    try:
        user  = User.objects.get(pk=user_id)
        asset = Asset.objects.get(ticker=ticker.upper())
    except User.DoesNotExist:
        logger.error('[run_backtest] User id=%d não encontrado.', user_id)
        return {'error': f'User {user_id} not found'}
    except Asset.DoesNotExist:
        logger.error('[run_backtest] Asset ticker=%s não encontrado.', ticker)
        return {'error': f'Asset {ticker} not found'}

    # ── 2. Carregar candles diários ────────────────────────────────────────────
    start = date.fromisoformat(start_date)
    end   = date.fromisoformat(end_date)

    candles_qs = (
        OHLCCandle.objects
        .filter(asset=asset, timeframe='1d', timestamp__date__gte=start, timestamp__date__lte=end)
        .order_by('timestamp')
        .values('timestamp', 'open', 'high', 'low', 'close', 'volume')
    )

    if not candles_qs.exists():
        logger.warning('[run_backtest] Sem candles para %s no período %s→%s.', ticker, start, end)
        return {'error': 'Sem dados OHLC para o período selecionado.'}

    df = pd.DataFrame(list(candles_qs))
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    df = df.sort_values('timestamp').reset_index(drop=True)
    for col in ('open', 'high', 'low', 'close', 'volume'):
        df[col] = df[col].astype(float)

    logger.info('[run_backtest] %s: %d candles carregados (%s → %s).', ticker, len(df), start, end)

    # ── 3. Aplicar estratégia e gerar sinais ───────────────────────────────────
    df = _apply_strategy(df, strategy)

    # ── 4. Simular trades ──────────────────────────────────────────────────────
    trades_log, final_capital = _simulate_trades(df, float(capital))

    # ── 5. Calcular métricas ───────────────────────────────────────────────────
    win_rate    = _calc_win_rate(trades_log)
    sharpe      = _calc_sharpe(trades_log, float(capital))
    max_dd      = _calc_max_drawdown(trades_log, float(capital))

    logger.info(
        '[run_backtest] %s | %s | Capital: R$%.2f → R$%.2f | WR=%.1f%% | Sharpe=%.2f | DD=%.1f%%',
        ticker, strategy, float(capital), final_capital, win_rate, sharpe, max_dd,
    )

    # ── 6. Persistir resultado ─────────────────────────────────────────────────
    result = BacktestResult.objects.create(
        user            = user,
        asset           = asset,
        strategy_name   = strategy,
        start_date      = start,
        end_date        = end,
        initial_capital = round(float(capital), 2),
        final_capital   = round(final_capital, 2),
        win_rate        = round(win_rate, 2),
        sharpe_ratio    = round(sharpe, 4),
        max_drawdown    = round(max_dd, 2),
        trades_log      = trades_log,
    )

    return {
        'status':        'ok',
        'result_id':     result.pk,
        'ticker':        ticker,
        'strategy':      strategy,
        'final_capital': round(final_capital, 2),
        'win_rate':      round(win_rate, 2),
        'sharpe':        round(sharpe, 4),
        'max_drawdown':  round(max_dd, 2),
        'trades':        len(trades_log),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Estratégias — geram coluna 'signal' (1=compra, -1=venda, 0=neutro)
# ─────────────────────────────────────────────────────────────────────────────

def _apply_strategy(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    """Adiciona coluna 'signal' ao DataFrame conforme a estratégia."""
    dispatch = {
        'sma_crossover':  _strat_sma_crossover,
        'rsi_reversal':   _strat_rsi_reversal,
        'macd_signal':    _strat_macd_signal,
        'bollinger_band': _strat_bollinger_band,
        'buy_and_hold':   _strat_buy_and_hold,
    }
    fn = dispatch.get(strategy, _strat_buy_and_hold)
    return fn(df)


def _strat_sma_crossover(df: pd.DataFrame) -> pd.DataFrame:
    """Cruzamento SMA 9/21: compra quando SMA9 > SMA21, vende quando SMA9 < SMA21."""
    df = df.copy()
    df['sma9']   = df['close'].rolling(9).mean()
    df['sma21']  = df['close'].rolling(21).mean()
    df['signal'] = 0
    df.loc[df['sma9'] > df['sma21'], 'signal'] =  1
    df.loc[df['sma9'] < df['sma21'], 'signal'] = -1
    return df


def _strat_rsi_reversal(df: pd.DataFrame) -> pd.DataFrame:
    """RSI 14: compra em sobrevendido (<30), vende em sobrecomprado (>70)."""
    df    = df.copy()
    delta = df['close'].diff()
    gain  = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs    = gain / loss.replace(0, float('nan'))
    rsi   = 100 - (100 / (1 + rs))
    df['rsi']    = rsi
    df['signal'] = 0
    df.loc[rsi < 30, 'signal'] =  1
    df.loc[rsi > 70, 'signal'] = -1
    return df


def _strat_macd_signal(df: pd.DataFrame) -> pd.DataFrame:
    """MACD (12,26,9): compra em cruzamento positivo, vende em cruzamento negativo."""
    df          = df.copy()
    ema12       = df['close'].ewm(span=12, adjust=False).mean()
    ema26       = df['close'].ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    df['macd_hist'] = macd_line - signal_line
    df['signal']    = 0
    df.loc[df['macd_hist'] > 0, 'signal'] =  1
    df.loc[df['macd_hist'] < 0, 'signal'] = -1
    return df


def _strat_bollinger_band(df: pd.DataFrame) -> pd.DataFrame:
    """Bollinger Bands (20, 2σ): compra em breakout acima da banda inferior, vende acima da superior."""
    df       = df.copy()
    mid      = df['close'].rolling(20).mean()
    std      = df['close'].rolling(20).std(ddof=0)
    upper    = mid + 2 * std
    lower    = mid - 2 * std
    df['signal'] = 0
    df.loc[df['close'] < lower, 'signal'] =  1
    df.loc[df['close'] > upper, 'signal'] = -1
    return df


def _strat_buy_and_hold(df: pd.DataFrame) -> pd.DataFrame:
    """Buy & Hold: compra no primeiro candle, segura até o final."""
    df           = df.copy()
    df['signal'] = 0
    if len(df) > 0:
        df.loc[df.index[0], 'signal'] = 1
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Simulação de trades
# ─────────────────────────────────────────────────────────────────────────────

def _simulate_trades(df: pd.DataFrame, capital: float) -> tuple[list[dict], float]:
    """
    Simula trades baseado na coluna 'signal' do DataFrame.

    Lógica simplificada:
        - Compra ao preço de fechamento quando signal muda de ≤0 para 1.
        - Venda ao preço de fechamento quando signal muda de 1 para ≤0.
        - Uma posição por vez (sem alavancagem).
        - Custos de transação: 0.1% por operação (corretagem + impostos).

    Returns:
        (trades_log, final_capital)
    """
    COST = 0.001   # 0.1% por operação

    trades     = []
    position   = None   # {'entry_price': float, 'entry_date': str, 'shares': float}
    prev_sig   = 0

    for _, row in df.iterrows():
        sig  = row.get('signal', 0)
        price = float(row['close'])
        ts    = str(row['timestamp'])[:10]

        # Compra
        if sig == 1 and prev_sig != 1 and position is None:
            cost_adj  = price * (1 + COST)
            shares    = capital / cost_adj
            position  = {'entry_price': cost_adj, 'entry_date': ts, 'shares': shares}

        # Venda
        elif sig != 1 and prev_sig == 1 and position is not None:
            exit_price = price * (1 - COST)
            pnl        = (exit_price - position['entry_price']) * position['shares']
            capital   += pnl
            trades.append({
                'entry_date':  position['entry_date'],
                'exit_date':   ts,
                'entry_price': round(position['entry_price'], 4),
                'exit_price':  round(exit_price, 4),
                'shares':      round(position['shares'], 6),
                'pnl':         round(pnl, 2),
                'pnl_pct':     round((exit_price / position['entry_price'] - 1) * 100, 2),
            })
            position = None

        prev_sig = sig

    # Fechar posição aberta no último candle
    if position is not None and len(df) > 0:
        last_price = float(df.iloc[-1]['close']) * (1 - COST)
        pnl        = (last_price - position['entry_price']) * position['shares']
        capital   += pnl
        trades.append({
            'entry_date':  position['entry_date'],
            'exit_date':   str(df.iloc[-1]['timestamp'])[:10],
            'entry_price': round(position['entry_price'], 4),
            'exit_price':  round(last_price, 4),
            'shares':      round(position['shares'], 6),
            'pnl':         round(pnl, 2),
            'pnl_pct':     round((last_price / position['entry_price'] - 1) * 100, 2),
        })

    return trades, max(capital, 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Métricas de desempenho
# ─────────────────────────────────────────────────────────────────────────────

def _calc_win_rate(trades: list[dict]) -> float:
    """Percentual de trades com PnL positivo."""
    if not trades:
        return 0.0
    winners = sum(1 for t in trades if t['pnl'] > 0)
    return (winners / len(trades)) * 100


def _calc_sharpe(trades: list[dict], initial_capital: float) -> float:
    """
    Índice de Sharpe anualizado baseado nos retornos dos trades.

    Sharpe = (mean_return - risk_free) / std_return * sqrt(252)
    """
    if len(trades) < 2:
        return 0.0

    returns = [t['pnl_pct'] / 100 for t in trades]
    mean_r  = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r    = math.sqrt(variance) if variance > 0 else 0

    if std_r == 0:
        return 0.0

    daily_rf = RISK_FREE_RATE / TRADING_DAYS
    return (mean_r - daily_rf) / std_r * math.sqrt(TRADING_DAYS)


def _calc_max_drawdown(trades: list[dict], initial_capital: float) -> float:
    """
    Drawdown máximo em percentual sobre o capital acumulado.

    Calcula a maior queda do pico para o vale na curva de capital.
    """
    if not trades:
        return 0.0

    capital    = initial_capital
    peak       = capital
    max_dd     = 0.0

    for trade in trades:
        capital += trade['pnl']
        peak     = max(peak, capital)
        drawdown = (peak - capital) / peak * 100 if peak > 0 else 0
        max_dd   = max(max_dd, drawdown)

    return max_dd
