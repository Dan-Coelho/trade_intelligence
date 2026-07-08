# news/utils.py — Utilitários do app de notícias
#
# Implementações:
#   4.4.2 — classify_sentiment(text): envia o título da notícia ao LLM configurado
#            (Google Gemini ou OpenAI) e retorna BULLISH / BEARISH / NEUTRAL

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Constantes ───────────────────────────────────────────────────────────────

VALID_SENTIMENTS = {'BULLISH', 'BEARISH', 'NEUTRAL'}

# Prompt do sistema enviado ao LLM para classificação de sentimento financeiro
SENTIMENT_SYSTEM_PROMPT = (
    'Você é um analista financeiro especializado no mercado brasileiro. '
    'Sua tarefa é classificar o sentimento de uma manchete financeira '
    'em relação ao mercado ou ativo mencionado. '
    'Responda APENAS com uma das três palavras: BULLISH, BEARISH ou NEUTRAL. '
    'Não adicione explicações, pontuação ou qualquer outro texto.'
)

# URLs das APIs de LLM suportadas
GEMINI_API_URL = (
    'https://generativelanguage.googleapis.com/v1beta/models/'
    'gemini-1.5-flash:generateContent'
)
OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions'


# ── Helpers privados ──────────────────────────────────────────────────────────

def _call_gemini(text: str, api_key: str) -> str:
    """Chama a API Google Gemini Flash para classificar o sentimento."""
    payload = {
        'system_instruction': {
            'parts': [{'text': SENTIMENT_SYSTEM_PROMPT}]
        },
        'contents': [
            {'parts': [{'text': text}]}
        ],
        'generationConfig': {
            'temperature': 0.0,
            'maxOutputTokens': 10,
        },
    }

    with httpx.Client(timeout=20) as client:
        response = client.post(
            GEMINI_API_URL,
            params={'key': api_key},
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    # Extrai o texto gerado da resposta Gemini
    try:
        return (
            data['candidates'][0]['content']['parts'][0]['text']
            .strip()
            .upper()
        )
    except (KeyError, IndexError) as exc:
        raise ValueError(f'Resposta Gemini inesperada: {data}') from exc


def _call_openai(text: str, api_key: str) -> str:
    """Chama a API OpenAI (gpt-4o-mini) para classificar o sentimento."""
    payload = {
        'model': 'gpt-4o-mini',
        'messages': [
            {'role': 'system', 'content': SENTIMENT_SYSTEM_PROMPT},
            {'role': 'user', 'content': text},
        ],
        'temperature': 0.0,
        'max_tokens': 10,
    }

    with httpx.Client(timeout=20) as client:
        response = client.post(
            OPENAI_API_URL,
            headers={'Authorization': f'Bearer {api_key}'},
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    try:
        return (
            data['choices'][0]['message']['content']
            .strip()
            .upper()
        )
    except (KeyError, IndexError) as exc:
        raise ValueError(f'Resposta OpenAI inesperada: {data}') from exc


# ── Função pública ────────────────────────────────────────────────────────────

def classify_sentiment(text: str) -> str:
    """
    Classifica o sentimento financeiro de um texto (tipicamente o título de
    uma notícia) usando o LLM configurado em settings.

    O provedor e a chave de API são lidos de:
        - settings.LLM_PROVIDER  ('google' ou 'openai')
        - settings.LLM_API_KEY

    Args:
        text: texto a ser classificado (título ou trecho da notícia).

    Returns:
        Uma string em maiúsculas: 'BULLISH', 'BEARISH' ou 'NEUTRAL'.
        Em caso de falha na chamada ao LLM, retorna 'NEUTRAL' como padrão seguro
        e registra o erro no logger.

    Examples:
        >>> classify_sentiment("Petrobras anuncia lucro recorde no trimestre")
        'BULLISH'
        >>> classify_sentiment("Queda brusca nas exportações preocupa governo")
        'BEARISH'
    """
    provider = getattr(settings, 'LLM_PROVIDER', 'google').lower()
    api_key = getattr(settings, 'LLM_API_KEY', '')

    if not api_key or api_key == 'your-llm-api-key-here':
        logger.warning(
            '[classify_sentiment] LLM_API_KEY não configurada. '
            'Retornando NEUTRAL como padrão.'
        )
        return 'NEUTRAL'

    try:
        if provider == 'openai':
            raw = _call_openai(text, api_key)
        else:
            # Padrão: Google Gemini
            raw = _call_gemini(text, api_key)

        # Valida que o retorno é um dos sentimentos esperados
        sentiment = raw.strip().upper()
        if sentiment not in VALID_SENTIMENTS:
            logger.warning(
                '[classify_sentiment] LLM retornou valor inesperado: %r. '
                'Usando NEUTRAL.',
                raw,
            )
            return 'NEUTRAL'

        return sentiment

    except httpx.HTTPStatusError as exc:
        logger.error(
            '[classify_sentiment] Erro HTTP %s ao chamar LLM: %s',
            exc.response.status_code, exc,
        )
    except httpx.TimeoutException:
        logger.error('[classify_sentiment] Timeout ao chamar LLM.')
    except Exception as exc:  # noqa: BLE001
        logger.error('[classify_sentiment] Erro inesperado: %s', exc)

    return 'NEUTRAL'
