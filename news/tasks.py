# news/tasks.py — Tasks Celery de coleta de notícias e dados macro
#
# Tarefas implementadas:
#   4.4.1 — fetch_news: scraping Investing.com (httpx + User-Agent rotation) com
#            fallback para NewsAPI; persistência em NewsArticle + classify_sentiment
#   4.5.1 — fetch_macro_data: integração API BCB para SELIC (série 432),
#            IPCA (série 433) e USD/BRL (série 1); upsert em MacroIndicator

import logging
import random
from datetime import datetime, timezone

import httpx
from celery import shared_task
from django.conf import settings
from django.utils.dateparse import parse_datetime

from market_data.models import Asset

from .models import MacroIndicator, NewsArticle
from .utils import classify_sentiment

logger = logging.getLogger(__name__)


# ── Constantes — fetch_news ──────────────────────────────────────────────────

# Pool de User-Agents para rotação (evita bloqueio por bot detection)
USER_AGENT_POOL = [
    (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) '
        'AppleWebKit/605.1.15 (KHTML, like Gecko) '
        'Version/17.3.1 Safari/605.1.15'
    ),
    (
        'Mozilla/5.0 (X11; Linux x86_64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/123.0.0.0 Safari/537.36'
    ),
    (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) '
        'Gecko/20100101 Firefox/125.0'
    ),
]

# Investing.com — URL base de busca de notícias por ticker
INVESTING_SEARCH_URL = 'https://www.investing.com/search/service/SearchInnerPage'

# NewsAPI — endpoint de busca de tudo
NEWSAPI_URL = 'https://newsapi.org/v2/everything'

# Chave NewsAPI lida do settings (opcional — fallback)
NEWSAPI_KEY = getattr(settings, 'NEWSAPI_KEY', '')

# Número máximo de artigos por ativo por execução
MAX_ARTICLES_PER_ASSET = 10

# Palavras-chave financeiras brasileiras adicionadas à busca para melhorar relevância
BR_FINANCIAL_KEYWORDS = ['bolsa', 'B3', 'ações', 'mercado', 'financeiro']


# ── Constantes — fetch_macro_data ─────────────────────────────────────────────

BCB_API_BASE = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}'

# Séries do Banco Central do Brasil usadas no sistema
BCB_SERIES = {
    'SELIC':  {'serie': 432,  'unit': '% a.a.'},
    'IPCA':   {'serie': 433,  'unit': '% a.m.'},
    'USD_BRL': {'serie': 1,   'unit': 'R$'},
}

# Número de últimas entradas a buscar por série
BCB_LAST_N = 5


# ── Helpers — fetch_news ─────────────────────────────────────────────────────

def _random_headers() -> dict:
    """Retorna headers HTTP com User-Agent aleatório do pool."""
    return {
        'User-Agent': random.choice(USER_AGENT_POOL),
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }


def _scrape_investing(ticker: str, client: httpx.Client) -> list[dict]:
    """
    Tenta buscar notícias do Investing.com para o ticker informado.

    Usa a API interna de busca do Investing.com com User-Agent rotation.
    Retorna lista de dicts com: title, body, source_url, source_name, published_at.
    Retorna lista vazia em caso de falha (para acionar o fallback).

    Args:
        ticker: código do ativo (ex: PETR4)
        client: instância httpx.Client compartilhada

    Returns:
        Lista de artigos encontrados (pode ser vazia).
    """
    try:
        # Investing.com tem proteção Cloudflare robusta em rotas diretas.
        # Usamos o endpoint de busca interno que é menos protegido.
        response = client.get(
            INVESTING_SEARCH_URL,
            params={
                'search_text': f'{ticker} bolsa',
                'tab':         'news',
                'isFilter':    'false',
            },
            headers={**_random_headers(), 'X-Requested-With': 'XMLHttpRequest'},
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        articles_raw = data.get('articles', [])
        if not articles_raw:
            logger.debug('[fetch_news] Investing.com: sem artigos para %s', ticker)
            return []

        articles = []
        for item in articles_raw[:MAX_ARTICLES_PER_ASSET]:
            title = item.get('title', '').strip()
            url   = item.get('link', '') or item.get('url', '')
            body  = item.get('description', '') or item.get('summary', '') or title

            # Parsing de data — Investing retorna epoch ou ISO 8601
            pub_raw = item.get('publishedAt') or item.get('date_utc') or item.get('pubDate')
            published_at = _parse_published_at(pub_raw)

            if not title or not url:
                continue

            articles.append({
                'title':        title,
                'body':         body,
                'source_url':   url,
                'source_name':  'Investing.com',
                'published_at': published_at,
            })

        logger.info(
            '[fetch_news] Investing.com: %d artigos para %s', len(articles), ticker
        )
        return articles

    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        logger.warning(
            '[fetch_news] Investing.com falhou para %s (%s). Acionando fallback.',
            ticker, exc,
        )
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            '[fetch_news] Investing.com erro inesperado para %s: %s. Fallback.',
            ticker, exc,
        )
        return []


def _fetch_newsapi(ticker: str, client: httpx.Client) -> list[dict]:
    """
    Busca notícias via NewsAPI como fallback do Investing.com.

    Requer que NEWSAPI_KEY esteja configurada em settings. Se ausente, retorna
    lista vazia e emite aviso.

    Args:
        ticker: código do ativo (ex: PETR4)
        client: instância httpx.Client compartilhada

    Returns:
        Lista de artigos encontrados (pode ser vazia).
    """
    api_key = getattr(settings, 'NEWSAPI_KEY', '')
    if not api_key:
        logger.warning(
            '[fetch_news] NEWSAPI_KEY não configurada. '
            'Fallback NewsAPI indisponível para %s.',
            ticker,
        )
        return []

    try:
        response = client.get(
            NEWSAPI_URL,
            params={
                'q':        f'{ticker} OR "{ticker} ações" OR "{ticker} bolsa"',
                'language': 'pt',
                'sortBy':   'publishedAt',
                'pageSize': MAX_ARTICLES_PER_ASSET,
                'apiKey':   api_key,
            },
            headers=_random_headers(),
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()

        articles = []
        for item in data.get('articles', []):
            title = (item.get('title') or '').strip()
            url   = item.get('url', '')
            body  = item.get('description') or item.get('content') or title
            pub_raw = item.get('publishedAt')
            published_at = _parse_published_at(pub_raw)

            if not title or not url or title == '[Removed]':
                continue

            articles.append({
                'title':        title,
                'body':         body or title,
                'source_url':   url,
                'source_name':  item.get('source', {}).get('name', 'NewsAPI'),
                'published_at': published_at,
            })

        logger.info(
            '[fetch_news] NewsAPI: %d artigos para %s', len(articles), ticker
        )
        return articles

    except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
        logger.error(
            '[fetch_news] NewsAPI falhou para %s: %s', ticker, exc
        )
        return []
    except Exception as exc:  # noqa: BLE001
        logger.error(
            '[fetch_news] NewsAPI erro inesperado para %s: %s', ticker, exc
        )
        return []


def _parse_published_at(raw) -> datetime:
    """
    Converte diferentes formatos de data/hora para datetime com timezone UTC.

    Suporta: epoch (int/float), string ISO 8601 e strings de datas comuns.
    Retorna datetime.now(UTC) se não for possível converter.
    """
    if raw is None:
        return datetime.now(timezone.utc)

    # Epoch timestamp
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        except (OSError, OverflowError):
            pass

    # String ISO 8601 (ex: "2024-04-20T15:30:00Z")
    if isinstance(raw, str):
        parsed = parse_datetime(raw)
        if parsed:
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed

    return datetime.now(timezone.utc)


def _persist_articles(asset: Asset | None, articles: list[dict]) -> int:
    """
    Persiste artigos no model NewsArticle.

    Usa source_url como chave de deduplicação — artigos com a mesma URL são
    ignorados (get_or_create). Para cada artigo novo, chama classify_sentiment
    para definir o campo sentiment.

    Args:
        asset: instância de Asset relacionada (pode ser None para notícias gerais)
        articles: lista de dicts com keys: title, body, source_url, source_name, published_at

    Returns:
        Número de artigos efetivamente criados (excluídas duplicatas).
    """
    created_count = 0
    for article in articles:
        title    = article['title']
        body     = article.get('body') or title
        url      = article['source_url']
        source   = article['source_name']
        pub_at   = article['published_at']

        # Verifica duplicata por URL antes de chamar o LLM (evita custo desnecessário)
        if NewsArticle.objects.filter(source_url=url).exists():
            continue

        # Classificação de sentimento via LLM
        sentiment = classify_sentiment(title)

        NewsArticle.objects.create(
            asset=asset,
            title=title,
            body=body,
            source_url=url,
            source_name=source,
            sentiment=sentiment,
            published_at=pub_at,
        )
        created_count += 1

    return created_count


# ── Task 4.4.1 — fetch_news ───────────────────────────────────────────────────

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name='news.tasks.fetch_news',
)
def fetch_news(self, ticker: str | None = None) -> dict:
    """
    Coleta notícias financeiras para os ativos cadastrados e persiste em NewsArticle.

    Estratégia de coleta (dois estágios):
    1. Tentativa principal: scraping Investing.com via httpx com User-Agent rotation.
    2. Fallback automático: NewsAPI (requer NEWSAPI_KEY em settings/env).

    Para cada artigo novo, chama classify_sentiment() (news/utils.py) para
    classificar o sentimento via LLM e persiste o resultado no campo `sentiment`.

    Args:
        ticker: se informado, processa apenas esse ativo; caso contrário, todos
                os ativos STOCK cadastrados serão processados.

    Returns:
        Dict com 'assets_processed', 'articles_created' e 'errors'.

    Retry Policy:
        - autoretry_for=(Exception,): retenta em qualquer exceção não tratada
        - max_retries=3
        - default_retry_delay=60 segundos
    """
    if ticker:
        assets = list(Asset.objects.filter(ticker__iexact=ticker))
    else:
        assets = list(Asset.objects.filter(asset_type=Asset.AssetType.STOCK))

    if not assets:
        logger.info(
            '[fetch_news] Nenhum ativo encontrado%s.',
            f' para ticker={ticker}' if ticker else '',
        )
        return {'assets_processed': 0, 'articles_created': 0, 'errors': 0}

    total_created = 0
    total_errors  = 0

    with httpx.Client(follow_redirects=True) as client:
        for asset in assets:
            asset_ticker = asset.ticker.upper()
            logger.info('[fetch_news] Buscando notícias para %s', asset_ticker)

            try:
                # Estágio 1: Investing.com
                articles = _scrape_investing(asset_ticker, client)

                # Estágio 2: fallback NewsAPI se Investing retornou vazio
                if not articles:
                    logger.info(
                        '[fetch_news] Acionando fallback NewsAPI para %s', asset_ticker
                    )
                    articles = _fetch_newsapi(asset_ticker, client)

                if not articles:
                    logger.warning(
                        '[fetch_news] Nenhuma notícia encontrada para %s '
                        '(Investing.com e NewsAPI indisponíveis ou sem resultados).',
                        asset_ticker,
                    )
                    continue

                created = _persist_articles(asset, articles)
                total_created += created

                logger.info(
                    '[fetch_news] %s: %d artigos novos criados (de %d coletados)',
                    asset_ticker, created, len(articles),
                )

            except Exception as exc:  # noqa: BLE001
                total_errors += 1
                logger.error(
                    '[fetch_news] Erro ao processar %s: %s', asset_ticker, exc
                )
                if ticker:
                    # Reraise para acionar retry somente em chamada single-ticker
                    raise

    logger.info(
        '[fetch_news] Concluído: %d ativos, %d artigos criados, %d erros.',
        len(assets), total_created, total_errors,
    )
    return {
        'assets_processed': len(assets),
        'articles_created': total_created,
        'errors':           total_errors,
    }


# ── Helpers — fetch_macro_data ────────────────────────────────────────────────

def _parse_bcb_date(date_str: str) -> 'date | None':
    """
    Converte a data retornada pela API BCB (formato DD/MM/YYYY) para objeto date.

    Args:
        date_str: string no formato 'DD/MM/YYYY' (ex: '07/07/2026')

    Returns:
        Objeto date ou None se não for possível converter.
    """
    from datetime import date as date_type  # noqa: PLC0415

    try:
        day, month, year = date_str.strip().split('/')
        return date_type(int(year), int(month), int(day))
    except (ValueError, AttributeError):
        logger.warning('[fetch_macro_data] Data BCB inválida: %r', date_str)
        return None


def _fetch_bcb_serie(name: str, serie: int, unit: str, last_n: int, client: httpx.Client) -> int:
    """
    Busca as últimas N entradas de uma série temporal do Banco Central (SGS) e
    faz upsert no model MacroIndicator.

    A API BCB retorna JSON no formato:
        [{"data": "DD/MM/YYYY", "valor": "12,34"}, ...]

    Args:
        name:    identificador do indicador (ex: 'SELIC', 'IPCA')
        serie:   número da série no SGS/BCB
        unit:    unidade de medida (ex: '% a.a.', 'R$')
        last_n:  quantidade de últimas entradas a buscar
        client:  instância httpx.Client compartilhada

    Returns:
        Número de registros processados (inseridos ou atualizados).
    """
    from decimal import Decimal, InvalidOperation  # noqa: PLC0415

    url = BCB_API_BASE.format(serie=serie, n=last_n)

    try:
        response = client.get(url, params={'formato': 'json'}, timeout=30)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error(
            '[fetch_macro_data] HTTP %s ao buscar série %s (serie=%d): %s',
            exc.response.status_code, name, serie, exc,
        )
        return 0
    except httpx.TimeoutException:
        logger.error(
            '[fetch_macro_data] Timeout ao buscar série %s (serie=%d)', name, serie
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        logger.error(
            '[fetch_macro_data] Erro inesperado para série %s (serie=%d): %s',
            name, serie, exc,
        )
        return 0

    if not isinstance(data, list) or not data:
        logger.warning(
            '[fetch_macro_data] Resposta vazia ou inválida para série %s', name
        )
        return 0

    count = 0
    for entry in data:
        date_str  = entry.get('data', '')
        valor_str = entry.get('valor', '')

        reference_date = _parse_bcb_date(date_str)
        if reference_date is None:
            continue

        # A API BCB retorna valores no formato brasileiro: '12,34' → Decimal('12.34')
        valor_clean = valor_str.strip().replace(',', '.')
        try:
            value = Decimal(valor_clean)
        except InvalidOperation:
            logger.warning(
                '[fetch_macro_data] Valor inválido para %s em %s: %r',
                name, date_str, valor_str,
            )
            continue

        MacroIndicator.objects.update_or_create(
            name=name,
            reference_date=reference_date,
            defaults={
                'source': f'Banco Central do Brasil — SGS série {serie}',
                'value':  value,
                'unit':   unit,
            },
        )
        count += 1

    logger.info(
        '[fetch_macro_data] Série %s (serie=%d): %d registros upserted.',
        name, serie, count,
    )
    return count


# ── Task 4.5.1 — fetch_macro_data ────────────────────────────────────────────

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name='news.tasks.fetch_macro_data',
)
def fetch_macro_data(self) -> dict:
    """
    Coleta indicadores macroeconômicos do Banco Central do Brasil (BCB/SGS) e
    persiste no model MacroIndicator.

    Indicadores coletados via API pública `api.bcb.gov.br/dados/serie`:
        - SELIC  (série 432) — Taxa básica de juros anualizada (% a.a.)
        - IPCA   (série 433) — Inflação mensal (% a.m.)
        - USD/BRL (série 1)  — Taxa de câmbio dólar/real (R$)

    Para cada série, busca as últimas BCB_LAST_N (5) entradas e faz upsert
    em MacroIndicator usando (name, reference_date) como chave única.

    A API BCB é pública, não requer autenticação e retorna JSON com datas no
    formato DD/MM/YYYY e valores decimais no formato brasileiro (vírgula).

    Returns:
        Dict com contagem de registros processados por série e total.

    Retry Policy:
        - autoretry_for=(Exception,): retenta em qualquer exceção não tratada
        - max_retries=3
        - default_retry_delay=60 segundos
    """
    logger.info('[fetch_macro_data] Iniciando coleta de dados macro (BCB/SGS).')

    results: dict[str, int] = {}
    total = 0

    with httpx.Client(follow_redirects=True) as client:
        for name, config in BCB_SERIES.items():
            count = _fetch_bcb_serie(
                name=name,
                serie=config['serie'],
                unit=config['unit'],
                last_n=BCB_LAST_N,
                client=client,
            )
            results[name] = count
            total += count

    logger.info(
        '[fetch_macro_data] Concluído: %d registros totais. Detalhes: %s',
        total, results,
    )
    return {'total': total, 'by_series': results}

