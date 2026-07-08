# market_data/tasks.py — Tasks Celery de coleta de dados OHLC
#
# Tarefas implementadas:
#   4.2.1 — fetch_intraday_ohlc: candles intraday via Brapi.dev (httpx)
#   4.2.2 — fetch_daily_ohlc: candles diários via yfinance

import logging
from datetime import datetime, timezone
from decimal import Decimal

import httpx
import yfinance as yf
from celery import shared_task
from django.utils import timezone as dj_timezone

from .models import Asset, OHLCCandle
from .utils import get_active_contract

logger = logging.getLogger(__name__)

# ── Constantes ───────────────────────────────────────────────────────────────

# URL base da API pública Brapi.dev
BRAPI_BASE_URL = 'https://brapi.dev/api'

# Timeframes Brapi → label interno
BRAPI_TIMEFRAME_MAP = {
    '1m':  '1m',
    '5m':  '5m',
    '15m': '15m',
    '1h':  '1h',
}

# Timeframes yfinance para coleta diária
YFINANCE_TIMEFRAME = '1d'
YFINANCE_PERIOD = '6mo'  # 6 meses de histórico


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_ticker_for_source(asset: Asset, source: str) -> str:
    """
    Resolve o ticker correto para cada fonte de dados.

    - Brapi.dev: tickers B3 sem sufixo (ex: PETR4), futuros como WINGR5
    - yfinance:  tickers B3 com sufixo .SA (ex: PETR4.SA), futuros como WIN=F
    """
    ticker = asset.ticker.upper()

    if asset.asset_type == Asset.AssetType.FUTURE:
        # Para futuros, usa o contrato ativo calculado por get_active_contract
        root = ticker[:3]  # WIN ou WDO
        try:
            active = get_active_contract(root)
        except ValueError:
            active = ticker

        if source == 'yfinance':
            # yfinance não suporta futuros B3 diretamente — usa ticker base
            # Formato aceito: WIN=F (Ibovespa) ou BRL=X (dólar)
            return f'{root}=F'
        return active

    # Ação: adiciona .SA no yfinance
    if source == 'yfinance':
        return f'{ticker}.SA'

    return ticker


def _upsert_candles(asset: Asset, timeframe: str, candles: list[dict]) -> int:
    """
    Insere ou atualiza candles no banco via update_or_create.

    Args:
        asset:     instância de Asset
        timeframe: string do timeframe ('1m', '5m', '15m', '1h', '1d')
        candles:   lista de dicts com chaves: timestamp, open, high, low, close, volume

    Returns:
        Número de candles processados.
    """
    count = 0
    for c in candles:
        ts = c['timestamp']
        # Garante datetime com timezone UTC
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        OHLCCandle.objects.update_or_create(
            asset=asset,
            timestamp=ts,
            timeframe=timeframe,
            defaults={
                'open':  Decimal(str(c['open'])),
                'high':  Decimal(str(c['high'])),
                'low':   Decimal(str(c['low'])),
                'close': Decimal(str(c['close'])),
                'volume': int(c.get('volume', 0)),
            },
        )
        count += 1

    return count


# ── Task 4.2.1 — fetch_intraday_ohlc via Brapi.dev ──────────────────────────

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name='market_data.tasks.fetch_intraday_ohlc',
)
def fetch_intraday_ohlc(self, timeframe: str = '15m') -> dict:
    """
    Coleta candles intraday para todos os ativos cadastrados via Brapi.dev.

    Usa httpx para requisição HTTP síncrona (Celery workers são síncronos por padrão).
    Após inserir os candles, dispara run_technical_analysis para cada ativo atualizado.

    Args:
        timeframe: intervalo dos candles. Padrão: '15m'.
                   Valores válidos: '1m', '5m', '15m', '1h'

    Returns:
        Dict com total de ativos processados e candles inseridos.
    """
    assets = Asset.objects.all()
    if not assets.exists():
        logger.info('[fetch_intraday_ohlc] Nenhum ativo cadastrado.')
        return {'assets': 0, 'candles': 0}

    total_candles = 0
    processed_assets = []

    with httpx.Client(timeout=30) as client:
        for asset in assets:
            ticker = _resolve_ticker_for_source(asset, 'brapi')

            try:
                response = client.get(
                    f'{BRAPI_BASE_URL}/quote/{ticker}',
                    params={
                        'interval': timeframe,
                        'range':    '1d',
                        'fundamental': 'false',
                    },
                )
                response.raise_for_status()
                data = response.json()

                results = data.get('results', [])
                if not results:
                    logger.warning(
                        '[fetch_intraday_ohlc] Sem dados para %s (timeframe=%s)',
                        ticker, timeframe,
                    )
                    continue

                historical = results[0].get('historicalDataPrice', [])
                if not historical:
                    logger.warning(
                        '[fetch_intraday_ohlc] historicalDataPrice vazio para %s',
                        ticker,
                    )
                    continue

                candles = [
                    {
                        'timestamp': datetime.fromtimestamp(
                            row['date'], tz=timezone.utc
                        ),
                        'open':   row.get('open')  or 0,
                        'high':   row.get('high')  or 0,
                        'low':    row.get('low')   or 0,
                        'close':  row.get('close') or 0,
                        'volume': row.get('volume', 0),
                    }
                    for row in historical
                    if row.get('open') and row.get('close')
                ]

                inserted = _upsert_candles(asset, timeframe, candles)
                total_candles += inserted
                processed_assets.append(asset.id)

                logger.info(
                    '[fetch_intraday_ohlc] %s: %d candles upserted (timeframe=%s)',
                    ticker, inserted, timeframe,
                )

            except httpx.HTTPStatusError as exc:
                logger.error(
                    '[fetch_intraday_ohlc] HTTP %s para %s: %s',
                    exc.response.status_code, ticker, exc,
                )
            except Exception as exc:
                logger.error(
                    '[fetch_intraday_ohlc] Erro inesperado para %s: %s',
                    ticker, exc,
                )

    # Dispara análise técnica para cada ativo atualizado (tarefa 4.6.1 usará signal,
    # mas chamamos explicitamente aqui como fallback seguro)
    if processed_assets:
        try:
            from analysis.tasks import run_technical_analysis  # noqa: PLC0415
            for asset_id in processed_assets:
                run_technical_analysis.delay(asset_id)
        except ImportError:
            # analysis.tasks ainda não existe (Sprint 5) — ignora silenciosamente
            logger.debug(
                '[fetch_intraday_ohlc] analysis.tasks não disponível ainda (Sprint 5).'
            )

    return {'assets': len(processed_assets), 'candles': total_candles}


# ── Task 4.2.2 — fetch_daily_ohlc via yfinance ──────────────────────────────

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name='market_data.tasks.fetch_daily_ohlc',
)
def fetch_daily_ohlc(self) -> dict:
    """
    Coleta candles diários (1d) para todos os ativos via yfinance.

    yfinance retorna um DataFrame pandas com colunas Open/High/Low/Close/Volume
    e índice DatetimeIndex. Converte para lista de dicts e chama _upsert_candles.

    Após inserção, dispara run_technical_analysis para cada ativo atualizado.

    Returns:
        Dict com total de ativos processados e candles inseridos.
    """
    assets = Asset.objects.all()
    if not assets.exists():
        logger.info('[fetch_daily_ohlc] Nenhum ativo cadastrado.')
        return {'assets': 0, 'candles': 0}

    total_candles = 0
    processed_assets = []

    for asset in assets:
        ticker_yf = _resolve_ticker_for_source(asset, 'yfinance')

        try:
            ticker_obj = yf.Ticker(ticker_yf)
            df = ticker_obj.history(
                period=YFINANCE_PERIOD,
                interval=YFINANCE_TIMEFRAME,
                auto_adjust=True,
            )

            if df.empty:
                logger.warning(
                    '[fetch_daily_ohlc] DataFrame vazio para %s', ticker_yf
                )
                continue

            # Normaliza colunas (yfinance pode retornar multi-index em alguns casos)
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

            # Garante que o índice tenha timezone UTC
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC')
            else:
                df.index = df.index.tz_convert('UTC')

            candles = []
            for ts, row in df.iterrows():
                open_val  = row.get('Open')
                close_val = row.get('Close')
                if open_val is None or close_val is None:
                    continue
                candles.append({
                    'timestamp': ts.to_pydatetime(),
                    'open':   float(open_val),
                    'high':   float(row.get('High', open_val)),
                    'low':    float(row.get('Low', open_val)),
                    'close':  float(close_val),
                    'volume': int(row.get('Volume', 0)),
                })

            inserted = _upsert_candles(asset, '1d', candles)
            total_candles += inserted
            processed_assets.append(asset.id)

            logger.info(
                '[fetch_daily_ohlc] %s: %d candles upserted (1d)',
                ticker_yf, inserted,
            )

        except Exception as exc:
            logger.error(
                '[fetch_daily_ohlc] Erro para %s: %s', ticker_yf, exc
            )

    # Dispara análise técnica para cada ativo atualizado
    if processed_assets:
        try:
            from analysis.tasks import run_technical_analysis  # noqa: PLC0415
            for asset_id in processed_assets:
                run_technical_analysis.delay(asset_id)
        except ImportError:
            logger.debug(
                '[fetch_daily_ohlc] analysis.tasks não disponível ainda (Sprint 5).'
            )

    return {'assets': len(processed_assets), 'candles': total_candles}
