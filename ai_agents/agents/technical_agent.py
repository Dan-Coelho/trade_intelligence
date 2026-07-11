"""
ai_agents/agents/technical_agent.py

Nó de análise técnica do grafo LangGraph.

Responsabilidade:
    - Buscar os últimos registros de TechnicalIndicator (RSI, MACD, Bollinger)
      e CandlestickPattern do banco de dados para o ativo solicitado.
    - Calcular os níveis de Fibonacci usando o range dos últimos candles.
    - Formatar tudo em um contexto textual estruturado.
    - Chamar o LLM (Google Gemini via langchain-google-genai) para gerar
      uma análise técnica em linguagem natural.
    - Retornar o estado atualizado com o campo `technical_analysis`.

Tarefa: 6.2.1
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from ai_agents.graph import AgentState

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constantes de configuração
# ─────────────────────────────────────────────────────────────────────────────

_MAX_INDICATORS = 5       # Número de registros por indicador a incluir no contexto
_MAX_PATTERNS = 10        # Número máximo de padrões de candle a incluir
_LLM_MODEL = "gemini-1.5-flash"  # Modelo padrão — pode ser sobrescrito por settings
_LLM_TEMPERATURE = 0.3   # Temperatura baixa para análise mais determinista

SYSTEM_PROMPT = """Você é um analista técnico especializado em mercado financeiro brasileiro.
Sua função é analisar indicadores técnicos e padrões de candle de um ativo e gerar
um parecer técnico claro, objetivo e fundamentado.

Regras:
- Use linguagem técnica, mas acessível ao trader.
- Cite os valores numéricos dos indicadores ao interpretar.
- Mencione os padrões de candle identificados e sua relevância.
- Conclua com uma perspectiva direcional (Alta, Baixa ou Neutro) com justificativa.
- Responda sempre em português brasileiro.
- Seja conciso: máximo de 300 palavras.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de busca no banco de dados
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_indicators(ticker: str) -> dict:
    """
    Busca os últimos registros de TechnicalIndicator por tipo de indicador.

    Retorna um dicionário com os últimos N registros para RSI, MACD e Bollinger.
    Importa os models dentro da função para evitar problemas de importação
    circular fora do contexto Django (grafo é importado por tasks, por exemplo).
    """
    from analysis.models import TechnicalIndicator  # noqa: PLC0415

    resultado = {}

    for nome in ("RSI", "MACD", "BOLLINGER"):
        registros = (
            TechnicalIndicator.objects
            .filter(asset__ticker=ticker, indicator_name=nome)
            .order_by("-timestamp")
            .values("timestamp", "timeframe", "values")
            [:_MAX_INDICATORS]
        )
        resultado[nome] = list(registros)

    return resultado


def _fetch_patterns(ticker: str) -> list:
    """Busca os últimos padrões de candlestick detectados para o ativo."""
    from analysis.models import CandlestickPattern  # noqa: PLC0415

    padroes = (
        CandlestickPattern.objects
        .filter(asset__ticker=ticker)
        .order_by("-timestamp")
        .values("timestamp", "timeframe", "pattern_name", "direction", "confidence")
        [:_MAX_PATTERNS]
    )
    return list(padroes)


def _fetch_fibonacci(ticker: str) -> dict | None:
    """
    Calcula os níveis de Fibonacci com base no high/low dos últimos candles diários.

    Retorna None se não houver dados suficientes.
    """
    from market_data.models import OHLCCandle  # noqa: PLC0415
    from analysis.utils import calculate_fibonacci_levels  # noqa: PLC0415

    candles = (
        OHLCCandle.objects
        .filter(asset__ticker=ticker, timeframe="1D")
        .order_by("-timestamp")
        .values("high", "low")
        [:50]  # Janela de 50 candles para calcular o swing high/low
    )

    if not candles:
        # Tenta outros timeframes como fallback
        candles = (
            OHLCCandle.objects
            .filter(asset__ticker=ticker)
            .order_by("-timestamp")
            .values("high", "low")
            [:50]
        )

    if not candles:
        return None

    highs = [float(c["high"]) for c in candles]
    lows  = [float(c["low"])  for c in candles]

    swing_high = max(highs)
    swing_low  = min(lows)

    if swing_high <= swing_low:
        return None

    try:
        return calculate_fibonacci_levels(swing_high, swing_low)
    except ValueError as exc:
        logger.warning("[technical_agent] Fibonacci ignorado: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Formatação do contexto para o LLM
# ─────────────────────────────────────────────────────────────────────────────

def _format_indicators(indicadores: dict) -> str:
    """Formata os indicadores técnicos como texto estruturado para o prompt."""
    linhas = []

    rsi_list = indicadores.get("RSI", [])
    if rsi_list:
        ultimo = rsi_list[0]
        rsi_val = ultimo["values"].get("rsi", "N/D")
        linhas.append(f"RSI (14) — último valor: {rsi_val} | Timeframe: {ultimo['timeframe']}")

    macd_list = indicadores.get("MACD", [])
    if macd_list:
        ultimo = macd_list[0]
        v = ultimo["values"]
        linhas.append(
            f"MACD (12,26,9) — MACD: {v.get('macd', 'N/D')} | "
            f"Sinal: {v.get('signal', 'N/D')} | "
            f"Histograma: {v.get('histogram', 'N/D')} | "
            f"Timeframe: {ultimo['timeframe']}"
        )

    boll_list = indicadores.get("BOLLINGER", [])
    if boll_list:
        ultimo = boll_list[0]
        v = ultimo["values"]
        linhas.append(
            f"Bollinger Bands (20,2) — Superior: {v.get('upper', 'N/D')} | "
            f"Média: {v.get('middle', 'N/D')} | "
            f"Inferior: {v.get('lower', 'N/D')} | "
            f"Timeframe: {ultimo['timeframe']}"
        )

    return "\n".join(linhas) if linhas else "Nenhum indicador técnico disponível."


def _format_patterns(padroes: list) -> str:
    """Formata os padrões de candle como texto para o prompt."""
    if not padroes:
        return "Nenhum padrão de candlestick identificado recentemente."

    linhas = []
    for p in padroes:
        confianca = float(p["confidence"])
        linhas.append(
            f"- {p['pattern_name']} ({p['direction']}, {confianca:.1f}% confiança) "
            f"em {p['timeframe']} — {p['timestamp']}"
        )
    return "\n".join(linhas)


def _format_fibonacci(niveis: dict | None) -> str:
    """Formata os níveis de Fibonacci como texto para o prompt."""
    if not niveis:
        return "Níveis de Fibonacci: dados insuficientes."

    linhas = ["Níveis de Fibonacci (swing high/low dos últimos 50 candles):"]
    for label, valor in niveis.items():
        linhas.append(f"  {label}: {valor:.4f}")
    return "\n".join(linhas)


def _build_prompt(ticker: str, indicadores: dict, padroes: list, fibonacci: dict | None) -> str:
    """Monta o prompt completo com todos os dados técnicos do ativo."""
    return f"""Ativo: {ticker}

=== INDICADORES TÉCNICOS ===
{_format_indicators(indicadores)}

=== PADRÕES DE CANDLESTICK ===
{_format_patterns(padroes)}

=== FIBONACCI ===
{_format_fibonacci(fibonacci)}

Com base nos dados acima, gere uma análise técnica completa e sua perspectiva direcional."""


# ─────────────────────────────────────────────────────────────────────────────
# Instância do LLM (lazy — criada na primeira chamada)
# ─────────────────────────────────────────────────────────────────────────────

_llm: ChatGoogleGenerativeAI | None = None


def _get_llm() -> ChatGoogleGenerativeAI:
    """Retorna a instância do LLM, criando-a na primeira chamada (lazy init)."""
    global _llm  # noqa: PLW0603
    if _llm is None:
        api_key = getattr(settings, "LLM_API_KEY", "")
        model   = getattr(settings, "LLM_MODEL", _LLM_MODEL)
        _llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=_LLM_TEMPERATURE,
        )
    return _llm


# ─────────────────────────────────────────────────────────────────────────────
# 6.2.1 — Nó principal: technical_node
# ─────────────────────────────────────────────────────────────────────────────

def technical_node(state: "AgentState") -> "AgentState":
    """
    Nó LangGraph de análise técnica.

    Fluxo:
        1. Extrai `ticker` do estado compartilhado.
        2. Busca TechnicalIndicator, CandlestickPattern e calcula Fibonacci.
        3. Formata um prompt de contexto técnico rico.
        4. Invoca o LLM para gerar a análise textual.
        5. Retorna o estado atualizado com `technical_analysis`.

    Em caso de erro (ex.: sem dados, LLM indisponível), retorna uma mensagem
    descritiva em `technical_analysis` sem interromper o pipeline.

    Args:
        state: estado compartilhado do grafo (AgentState TypedDict).

    Returns:
        Estado atualizado com o campo `technical_analysis` preenchido.
    """
    ticker = state.get("ticker", "")
    logger.info("[technical_agent] Iniciando análise técnica para %s", ticker)

    # ── 1. Buscar dados do banco ───────────────────────────────────────────
    try:
        indicadores = _fetch_indicators(ticker)
        padroes     = _fetch_patterns(ticker)
        fibonacci   = _fetch_fibonacci(ticker)
    except Exception as exc:  # noqa: BLE001
        logger.error("[technical_agent] Erro ao buscar dados do banco: %s", exc)
        return {**state, "technical_analysis": f"Erro ao buscar dados técnicos: {exc}"}

    # ── 2. Montar prompt ───────────────────────────────────────────────────
    prompt_usuario = _build_prompt(ticker, indicadores, padroes, fibonacci)

    # ── 3. Chamar LLM ─────────────────────────────────────────────────────
    try:
        llm = _get_llm()
        mensagens = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt_usuario),
        ]
        resposta = llm.invoke(mensagens)
        analise  = resposta.content
        logger.info("[technical_agent] Análise gerada com sucesso para %s", ticker)
    except Exception as exc:  # noqa: BLE001
        logger.error("[technical_agent] Erro ao chamar LLM: %s", exc)
        analise = f"Erro ao gerar análise técnica via LLM: {exc}"

    # ── 4. Retornar estado atualizado ──────────────────────────────────────
    return {**state, "technical_analysis": analise}
