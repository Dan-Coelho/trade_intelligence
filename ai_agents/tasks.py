# ai_agents/tasks.py — Task Celery para execução do grafo multi-agente IA
#
# Implementações:
#   6.6.1 — run_ai_analysis(asset_id): instancia o grafo LangGraph, executa
#            com estado inicial e persiste o resultado em AISignal.
#   6.7.2 — Verifica cache `ai_signal_{asset_id}` antes de executar o grafo;
#            salva resultado no cache por 300 segundos após execução.
#   7.1.5 — Após persistir o sinal, publica resultado no channel group
#            `asset_{ticker}` via channels.layers.get_channel_layer().group_send().

import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Chave de cache e TTL (6.7.2)
_CACHE_KEY_TEMPLATE = 'ai_signal_{asset_id}'
_CACHE_TTL          = 300  # segundos — 5 minutos


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name='ai_agents.tasks.run_ai_analysis',
)
def run_ai_analysis(self, asset_id: int) -> dict:
    """
    Executa o pipeline multi-agente LangGraph para um ativo e persiste o
    resultado em AISignal.

    Fluxo:
        1. Verifica cache Redis `ai_signal_{asset_id}` — retorna imediatamente
           se o sinal ainda estiver em cache (TTL 300 s).
        2. Busca o Asset pelo asset_id.
        3. Monta o estado inicial (AgentState) com ticker e asset_type.
        4. Importa e instancia o grafo compilado (build_graph().compile()).
        5. Executa o grafo (invoke) — os nós supervisor, technical, fundamental,
           macro e synthesis rodam em sequência/paralelo conforme o tipo do ativo.
        6. O nó synthesis_node persiste o resultado em AISignal.
        7. Salva o resultado no cache Redis por 300 segundos.
        8. Publica o sinal no channel group `asset_{ticker}` via Channels (7.1.5).

    Args:
        asset_id: PK do model Asset a analisar.

    Returns:
        Dict com status, ticker, signal, confidence e synthesis.
        Em caso de cache hit, retorna o resultado cacheado com source='cache'.
        Em caso de erro, retorna dict com chave 'error'.
    """
    cache_key = _CACHE_KEY_TEMPLATE.format(asset_id=asset_id)

    # ── 1. Verificar cache (6.7.2) ─────────────────────────────────────────────
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logger.debug(
            '[run_ai_analysis] Cache hit para asset_id=%d — retornando resultado cacheado.',
            asset_id,
        )
        cached_result['source'] = 'cache'
        return cached_result

    # ── 2. Buscar Asset ────────────────────────────────────────────────────────
    from market_data.models import Asset  # noqa: PLC0415

    try:
        asset = Asset.objects.select_related().get(pk=asset_id)
    except Asset.DoesNotExist:
        logger.error('[run_ai_analysis] Asset id=%d não encontrado.', asset_id)
        return {'error': f'Asset {asset_id} not found'}

    ticker     = asset.ticker
    asset_type = getattr(asset, 'asset_type', 'STOCK')

    logger.info(
        '[run_ai_analysis] Iniciando análise IA para %s (asset_id=%d, tipo=%s)',
        ticker, asset_id, asset_type,
    )

    # ── 3. Montar estado inicial ───────────────────────────────────────────────
    initial_state = {
        'ticker':               ticker,
        'asset_type':           asset_type,
        'technical_analysis':   None,
        'fundamental_analysis': None,
        'macro_analysis':       None,
        'signal':               None,
        'confidence':           None,
        'synthesis':            None,
    }

    # ── 4. Importar e executar o grafo ─────────────────────────────────────────
    # Importação local — o grafo pode ter dependências pesadas (LangGraph, LLMs)
    # que não devem ser carregadas no processo principal do Django.
    from ai_agents.graph import build_graph  # noqa: PLC0415

    try:
        compiled    = build_graph().compile()
        final_state = compiled.invoke(initial_state)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            '[run_ai_analysis] Erro ao executar grafo para %s: %s',
            ticker, exc,
        )
        raise  # Celery autoretry_for irá capturar e reagendar

    signal     = final_state.get('signal',     'NEUTRAL')
    confidence = final_state.get('confidence', 0.0)
    synthesis  = final_state.get('synthesis',  '')

    logger.info(
        '[run_ai_analysis] Análise concluída — %s | %s | %.1f%%',
        ticker, signal, confidence or 0,
    )

    # ── 5. Montar resultado e salvar no cache (6.7.2) ──────────────────────────
    result = {
        'status':     'ok',
        'source':     'graph',
        'asset':      ticker,
        'asset_id':   asset_id,
        'signal':     signal,
        'confidence': confidence,
        'synthesis':  (synthesis or '')[:300],  # trunca para não poluir logs/cache
    }

    try:
        cache.set(cache_key, result, timeout=_CACHE_TTL)
        logger.debug(
            '[run_ai_analysis] Resultado salvo no cache Redis — key=%s, TTL=%ds.',
            cache_key, _CACHE_TTL,
        )
    except Exception as exc:  # noqa: BLE001
        # Falha de cache não deve interromper o fluxo principal
        logger.warning(
            '[run_ai_analysis] Não foi possível salvar no cache Redis: %s', exc,
        )

    # ── 6. Publicar no channel group para atualização WebSocket (7.1.5) ────────
    # Celery workers são síncronos; usamos async_to_sync para chamar a API
    # assíncrona do Channel Layer a partir de um contexto síncrono.
    _publish_to_channel(ticker, signal, confidence, synthesis)

    return result


def _publish_to_channel(
    ticker: str,
    signal: str,
    confidence: float | None,
    synthesis: str | None,
) -> None:
    """
    Publica o sinal IA no channel group `asset_{ticker}` via Django Channels.

    Todos os AssetConsumers conectados ao grupo receberão a mensagem e a
    encaminharão via WebSocket para seus respectivos clientes.

    A publicação é feita com async_to_sync para compatibilidade com o
    contexto síncrono do worker Celery.

    Args:
        ticker:     código do ativo (ex.: PETR4).
        signal:     sinal direcional (BULLISH | BEARISH | NEUTRAL).
        confidence: confiança do sinal em % (0–100).
        synthesis:  texto de síntese do sinal.
    """
    try:
        from channels.layers import get_channel_layer  # noqa: PLC0415

        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning(
                '[run_ai_analysis] Channel layer não configurado — '
                'sinal não publicado via WebSocket.'
            )
            return

        group_name = f'asset_{ticker}'
        message = {
            'type':       'ai_signal',   # mapeia para AssetConsumer.ai_signal()
            'ticker':     ticker,
            'signal':     signal,
            'confidence': confidence or 0,
            'synthesis':  (synthesis or '')[:300],
        }

        async_to_sync(channel_layer.group_send)(group_name, message)

        logger.debug(
            '[run_ai_analysis] Sinal publicado no channel group %s — %s | %.1f%%',
            group_name, signal, confidence or 0,
        )
    except Exception as exc:  # noqa: BLE001
        # Falha de publicação não deve interromper o retorno da task
        logger.error(
            '[run_ai_analysis] Erro ao publicar no channel group asset_%s: %s',
            ticker, exc,
        )
