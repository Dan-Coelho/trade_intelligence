# fundamentals/tasks.py — Task Celery de coleta de dados fundamentalistas
#
# Tarefas implementadas:
#   4.3.1 — fetch_fundamentals: scraping do Fundamentus via httpx + BeautifulSoup4,
#            parsing de P/L, ROE, DY, EV/EBITDA, upsert no model FundamentalData
#   4.3.2 — retry logic: autoretry_for=(Exception,), max_retries=3, default_retry_delay=60

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx
from bs4 import BeautifulSoup
from celery import shared_task

from market_data.models import Asset

from .models import FundamentalData

logger = logging.getLogger(__name__)

# ── Constantes ───────────────────────────────────────────────────────────────

FUNDAMENTUS_URL = 'https://www.fundamentus.com.br/detalhes.php'

# Headers que simulam um browser comum para evitar bloqueio 403
FUNDAMENTUS_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://www.fundamentus.com.br/',
}

# Mapeamento dos rótulos exibidos no Fundamentus para os campos do model.
# Chave: texto (ou parte do texto) da célula de rótulo (case-insensitive).
# Valor: nome do campo no model FundamentalData.
FIELD_MAP = {
    'p/l':         'pl_ratio',
    'roe':         'roe',
    'div. yield':  'dividend_yield',
    'ev/ebitda':   'ev_ebitda',
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_br_number(text: str) -> Decimal | None:
    """
    Converte um número no formato brasileiro para Decimal.

    Exemplos de entrada: '12,34', '1.234,56', '5,60%', '-'
    Retorna None se não for possível converter.
    """
    if not text:
        return None

    # Remove espaços, sinal de porcentagem e outros caracteres não numéricos
    cleaned = text.strip().replace('%', '').replace('\xa0', '').strip()

    # Trata traço ou valores nulos
    if cleaned in ('-', '', 'n/d', 'N/D', '0'):
        return None

    # Formato BR: separador de milhar = '.', decimal = ','
    # Remove separador de milhar e substitui vírgula por ponto
    cleaned = cleaned.replace('.', '').replace(',', '.')

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _scrape_fundamentus(ticker: str) -> dict:
    """
    Faz o scraping da página de detalhes do Fundamentus para o ticker informado.

    Args:
        ticker: código do ativo na B3 (ex: PETR4, VALE3)

    Returns:
        Dict com os campos extraídos. Campos não encontrados ficam como None.
        Sempre inclui 'raw_data' com todos os pares rótulo→valor da página.

    Raises:
        httpx.HTTPStatusError: quando o Fundamentus retorna status de erro.
        ValueError: quando a página não contém tabela de indicadores válida.
    """
    with httpx.Client(timeout=30, headers=FUNDAMENTUS_HEADERS, follow_redirects=True) as client:
        response = client.get(FUNDAMENTUS_URL, params={'papel': ticker.upper()})
        response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')

    # O Fundamentus organiza os indicadores em tabelas com células <td class="label">
    # e <td class="data">. Iteramos sobre todos os pares label→data.
    label_cells = soup.find_all('td', class_='label')

    if not label_cells:
        raise ValueError(
            f'[fetch_fundamentals] Estrutura de tabela não encontrada para {ticker}. '
            'O Fundamentus pode ter alterado o layout ou o ticker é inválido.'
        )

    raw_data: dict[str, str] = {}
    result: dict[str, Decimal | None] = {
        'pl_ratio':       None,
        'roe':            None,
        'dividend_yield': None,
        'ev_ebitda':      None,
    }

    for label_td in label_cells:
        label_text = label_td.get_text(strip=True)
        data_td = label_td.find_next_sibling('td', class_='data')
        if data_td is None:
            continue

        data_text = data_td.get_text(strip=True)
        raw_data[label_text] = data_text

        # Normaliza o rótulo para comparação (minúsculas, sem espaços extras)
        label_norm = re.sub(r'\s+', ' ', label_text.lower()).strip()

        for key, field_name in FIELD_MAP.items():
            if key in label_norm:
                result[field_name] = _parse_br_number(data_text)
                break

    result['raw_data'] = raw_data  # type: ignore[assignment]
    return result


# ── Task 4.3.1 + 4.3.2 — fetch_fundamentals ─────────────────────────────────

@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name='fundamentals.tasks.fetch_fundamentals',
)
def fetch_fundamentals(self, ticker: str | None = None) -> dict:
    """
    Coleta dados fundamentalistas do Fundamentus e persiste no model FundamentalData.

    Realiza scraping da página de detalhes do Fundamentus para cada ativo do tipo
    STOCK cadastrado no banco (ou apenas para o ticker informado, se passado).

    Indicadores coletados:
        - P/L  (pl_ratio)
        - ROE  (roe)
        - Dividend Yield  (dividend_yield)
        - EV/EBITDA  (ev_ebitda)

    Os dados são upsert no banco usando (asset, reference_date) como chave única,
    onde reference_date é a data atual (os dados do Fundamentus refletem o presente).

    Args:
        ticker: se informado, processa apenas esse ativo; caso contrário, todos os
                ativos do tipo STOCK cadastrados serão processados.

    Returns:
        Dict com 'assets_processed' e 'errors'.

    Retry Policy (4.3.2):
        - autoretry_for=(Exception,): retenta em qualquer exceção não tratada
        - max_retries=3: até 3 tentativas após a falha inicial
        - default_retry_delay=60: aguarda 60 segundos entre tentativas
    """
    # Seleciona ativos a processar
    if ticker:
        assets = Asset.objects.filter(
            ticker__iexact=ticker,
            asset_type=Asset.AssetType.STOCK,
        )
    else:
        assets = Asset.objects.filter(asset_type=Asset.AssetType.STOCK)

    if not assets.exists():
        logger.info(
            '[fetch_fundamentals] Nenhum ativo STOCK encontrado%s.',
            f' para ticker={ticker}' if ticker else '',
        )
        return {'assets_processed': 0, 'errors': 0}

    today = date.today()
    processed = 0
    errors = 0

    for asset in assets:
        asset_ticker = asset.ticker.upper()
        logger.info('[fetch_fundamentals] Iniciando scraping para %s', asset_ticker)

        try:
            scraped = _scrape_fundamentus(asset_ticker)

            raw_data = scraped.pop('raw_data', {})

            FundamentalData.objects.update_or_create(
                asset=asset,
                reference_date=today,
                defaults={
                    'pl_ratio':       scraped.get('pl_ratio'),
                    'roe':            scraped.get('roe'),
                    'dividend_yield': scraped.get('dividend_yield'),
                    'ev_ebitda':      scraped.get('ev_ebitda'),
                    'raw_data':       raw_data,
                },
            )

            processed += 1
            logger.info(
                '[fetch_fundamentals] %s: P/L=%s | ROE=%s | DY=%s | EV/EBITDA=%s',
                asset_ticker,
                scraped.get('pl_ratio'),
                scraped.get('roe'),
                scraped.get('dividend_yield'),
                scraped.get('ev_ebitda'),
            )

        except httpx.HTTPStatusError as exc:
            errors += 1
            logger.error(
                '[fetch_fundamentals] HTTP %s ao buscar %s: %s',
                exc.response.status_code, asset_ticker, exc,
            )

        except ValueError as exc:
            errors += 1
            logger.error(
                '[fetch_fundamentals] Erro de parsing para %s: %s',
                asset_ticker, exc,
            )

        except Exception as exc:  # noqa: BLE001
            errors += 1
            logger.error(
                '[fetch_fundamentals] Erro inesperado para %s: %s',
                asset_ticker, exc,
            )
            # Re-lança para que o autoretry_for do Celery entre em ação
            # somente quando processamos um único ticker (falha crítica)
            if ticker:
                raise

    logger.info(
        '[fetch_fundamentals] Concluído: %d processados, %d erros.',
        processed, errors,
    )
    return {'assets_processed': processed, 'errors': errors}
