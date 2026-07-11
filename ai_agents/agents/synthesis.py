"""
ai_agents/agents/synthesis.py

Nó de síntese e sinalização final do grafo LangGraph.

Responsabilidade:
    - Receber as três análises produzidas pelos agentes anteriores:
        * technical_analysis  (sempre presente)
        * fundamental_analysis (vazio para contratos futuros)
        * macro_analysis      (sempre presente)
    - Chamar o LLM para consolidar as análises e emitir:
        * Sinal direcional: BULLISH | BEARISH | NEUTRAL
        * Confiança: 0–100 (float)
        * Texto de síntese: parágrafo unificado
    - Persistir o resultado no model `AISignal` do banco de dados.
    - Retornar o estado atualizado com `signal`, `confidence` e `synthesis`.

Tarefa: 6.5.2
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
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

_LLM_MODEL       = "gemini-1.5-flash"
_LLM_TEMPERATURE = 0.2   # Temperatura mais baixa para saída estruturada (JSON)

SYSTEM_PROMPT = """Você é um analista-chefe de investimentos responsável por consolidar
análises técnica, fundamentalista e macroeconômica em um sinal de investimento final.

Sua tarefa:
1. Ler as análises fornecidas (técnica, fundamentalista e macro).
2. Ponderar cada dimensão e chegar a um consenso direcional.
3. Responder EXCLUSIVAMENTE com um objeto JSON válido, sem texto extra, no formato:

{
  "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": <número de 0 a 100>,
  "synthesis": "<texto de síntese em português, máximo 250 palavras>"
}

Critérios de confiança:
- 80–100: forte convergência entre as três análises
- 60–79:  convergência parcial (2 de 3)
- 40–59:  sinais mistos
- 20–39:  leve divergência
- 0–19:   forte divergência / dados insuficientes

Responda SOMENTE com o JSON, sem markdown, sem código, sem explicações adicionais.
"""

# Regex para extrair JSON da resposta do LLM (tolerante a markdown code blocks)
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

# Valores válidos para o campo signal
_VALID_SIGNALS = {"BULLISH", "BEARISH", "NEUTRAL"}


# ─────────────────────────────────────────────────────────────────────────────
# Formatação do contexto para o LLM
# ─────────────────────────────────────────────────────────────────────────────

def _build_prompt(state: "AgentState") -> str:
    """Monta o prompt com as três análises para o LLM sintetizar."""
    ticker     = state.get("ticker", "")
    asset_type = state.get("asset_type", "")

    tecnica        = state.get("technical_analysis")   or "Análise técnica não disponível."
    fundamentalista = state.get("fundamental_analysis") or (
        "Análise fundamentalista não aplicável (contrato futuro)."
        if asset_type != "STOCK"
        else "Análise fundamentalista não disponível."
    )
    macro = state.get("macro_analysis") or "Análise macroeconômica não disponível."

    return f"""Ativo: {ticker} (tipo: {asset_type})

=== ANÁLISE TÉCNICA ===
{tecnica}

=== ANÁLISE FUNDAMENTALISTA ===
{fundamentalista}

=== ANÁLISE MACRO / NOTÍCIAS ===
{macro}

Consolide as análises acima e retorne o JSON com o sinal final."""


# ─────────────────────────────────────────────────────────────────────────────
# Parser da resposta do LLM
# ─────────────────────────────────────────────────────────────────────────────

def _parse_llm_response(raw: str) -> tuple[str, float, str]:
    """
    Extrai (signal, confidence, synthesis) da resposta JSON do LLM.

    Tolerante a markdown code blocks e texto extra ao redor do JSON.

    Returns:
        Tupla (signal, confidence, synthesis).
        Em caso de falha no parse, retorna valores neutros seguros.
    """
    match = _JSON_RE.search(raw)
    if not match:
        logger.warning("[synthesis] Resposta do LLM não contém JSON válido: %s", raw[:200])
        return "NEUTRAL", 0.0, raw[:500]

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as exc:
        logger.warning("[synthesis] Falha ao decodificar JSON do LLM: %s", exc)
        return "NEUTRAL", 0.0, raw[:500]

    signal = str(data.get("signal", "NEUTRAL")).upper()
    if signal not in _VALID_SIGNALS:
        logger.warning("[synthesis] Sinal inválido recebido do LLM: '%s' → NEUTRAL", signal)
        signal = "NEUTRAL"

    try:
        confidence = float(data.get("confidence", 0))
        confidence = max(0.0, min(100.0, confidence))   # clamp 0–100
    except (TypeError, ValueError):
        confidence = 0.0

    synthesis = str(data.get("synthesis", "Síntese não disponível."))

    return signal, confidence, synthesis


# ─────────────────────────────────────────────────────────────────────────────
# Persistência no banco de dados
# ─────────────────────────────────────────────────────────────────────────────

def _persist_ai_signal(
    ticker: str,
    asset_type: str,
    signal: str,
    confidence: float,
    synthesis: str,
    state: "AgentState",
) -> None:
    """
    Persiste o sinal gerado no model AISignal.

    Usa `update_or_create` com chave (asset, generated_at truncado ao minuto)
    para evitar duplicatas em re-execuções próximas.

    Importação local para evitar problemas de contexto Django.
    """
    from ai_agents.models import AISignal       # noqa: PLC0415
    from market_data.models import Asset        # noqa: PLC0415

    try:
        asset = Asset.objects.get(ticker=ticker)
    except Asset.DoesNotExist:
        logger.warning("[synthesis] Asset '%s' não encontrado — sinal não persistido.", ticker)
        return
    except Exception as exc:  # noqa: BLE001
        logger.error("[synthesis] Erro ao buscar Asset '%s': %s", ticker, exc)
        return

    now = datetime.now(tz=timezone.utc)

    # Timeframe inferido do estado (fallback para "multi")
    timeframe = "multi"

    try:
        AISignal.objects.update_or_create(
            asset=asset,
            generated_at__date=now.date(),
            defaults={
                "signal_type":              signal,
                "confidence_pct":           round(confidence, 2),
                "technical_justification":  state.get("technical_analysis")   or "",
                "fundamental_justification": state.get("fundamental_analysis") or "",
                "macro_justification":      state.get("macro_analysis")        or "",
                "synthesis_text":           synthesis,
                "timeframe":                timeframe,
                "generated_at":             now,
            },
        )
        logger.info(
            "[synthesis] AISignal persistido — %s | %s | %.1f%%",
            ticker, signal, confidence,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[synthesis] Erro ao persistir AISignal: %s", exc)


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
# 6.5.2 — Nó principal: synthesis_node
# ─────────────────────────────────────────────────────────────────────────────

def synthesis_node(state: "AgentState") -> "AgentState":
    """
    Nó LangGraph de síntese e sinalização final.

    Consolida as análises técnica, fundamentalista e macro produzidas
    pelos agentes anteriores em um único sinal de investimento com
    confiança e texto de síntese. Persiste o resultado em AISignal.

    Fluxo:
        1. Extrai as três análises do estado compartilhado.
        2. Monta prompt de consolidação para o LLM.
        3. Invoca o LLM esperando resposta JSON estruturada.
        4. Parseia (signal, confidence, synthesis) da resposta.
        5. Persiste o resultado em AISignal no banco de dados.
        6. Retorna o estado atualizado com signal, confidence e synthesis.

    Em caso de erro no LLM, retorna NEUTRAL com confiança 0
    sem interromper o pipeline.

    Args:
        state: estado compartilhado do grafo (AgentState TypedDict).

    Returns:
        Estado atualizado com `signal`, `confidence` e `synthesis`.
    """
    ticker     = state.get("ticker", "")
    asset_type = state.get("asset_type", "")

    logger.info("[synthesis] Iniciando síntese final para %s", ticker)

    # ── 1. Montar prompt ───────────────────────────────────────────────────
    prompt_usuario = _build_prompt(state)

    # ── 2. Chamar LLM ─────────────────────────────────────────────────────
    signal, confidence, synthesis = "NEUTRAL", 0.0, "Análise não disponível."

    try:
        llm = _get_llm()
        mensagens = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt_usuario),
        ]
        resposta = llm.invoke(mensagens)
        signal, confidence, synthesis = _parse_llm_response(resposta.content)
        logger.info(
            "[synthesis] Sinal gerado — %s | %s | %.1f%%",
            ticker, signal, confidence,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("[synthesis] Erro ao chamar LLM: %s", exc)
        synthesis = f"Erro ao gerar síntese via LLM: {exc}"

    # ── 3. Persistir no banco ──────────────────────────────────────────────
    _persist_ai_signal(ticker, asset_type, signal, confidence, synthesis, state)

    # ── 4. Retornar estado atualizado ──────────────────────────────────────
    return {
        **state,
        "signal":     signal,
        "confidence": confidence,
        "synthesis":  synthesis,
    }
