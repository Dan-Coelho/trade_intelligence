"""
ai_agents/agents/fundamental_agent.py

Nó de análise fundamentalista do grafo LangGraph.

Responsabilidade:
    - Executado APENAS quando `asset_type == 'STOCK'` (ações).
      Contratos futuros (WIN, WDO, etc.) não possuem dados fundamentalistas.
    - Busca os registros mais recentes de FundamentalData do banco de dados.
    - Formata os indicadores (P/L, ROE, DY, EV/EBITDA) em contexto textual.
    - Chama o LLM (Google Gemini via langchain-google-genai) para gerar
      uma análise fundamentalista em linguagem natural.
    - Retorna o estado atualizado com o campo `fundamental_analysis`.

Tarefa: 6.3.1
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

_MAX_RECORDS = 4          # Últimos N registros fundamentalistas a incluir no contexto
_LLM_MODEL = "gemini-1.5-flash"
_LLM_TEMPERATURE = 0.3

SYSTEM_PROMPT = """Você é um analista fundamentalista especializado em ações do mercado brasileiro (B3).
Sua função é interpretar indicadores fundamentalistas de uma empresa e gerar um
parecer objetivo sobre a qualidade do ativo do ponto de vista fundamentalista.

Regras:
- Cite os valores numéricos dos indicadores (P/L, ROE, Dividend Yield, EV/EBITDA).
- Compare com referências do mercado quando relevante (ex.: P/L < 10 pode indicar subvalorização).
- Avalie a atratividade do ativo para investimento de médio/longo prazo.
- Conclua com uma perspectiva fundamentalista (Positivo, Negativo ou Neutro) com justificativa.
- Responda sempre em português brasileiro.
- Seja conciso: máximo de 300 palavras.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de busca no banco de dados
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_fundamental_data(ticker: str) -> list[dict]:
    """
    Busca os últimos N registros de FundamentalData para o ativo.

    Importação local para evitar problemas de importação circular fora
    do contexto Django (o grafo pode ser importado antes do setup do ORM).
    """
    from fundamentals.models import FundamentalData  # noqa: PLC0415

    registros = (
        FundamentalData.objects
        .filter(asset__ticker=ticker)
        .order_by("-reference_date")
        .values(
            "reference_date",
            "pl_ratio",
            "roe",
            "dividend_yield",
            "ev_ebitda",
            "raw_data",
        )
        [:_MAX_RECORDS]
    )
    return list(registros)


# ─────────────────────────────────────────────────────────────────────────────
# Formatação do contexto para o LLM
# ─────────────────────────────────────────────────────────────────────────────

def _fmt(valor, sufixo: str = "", casas: int = 2) -> str:
    """Formata um valor Decimal/None para exibição amigável."""
    if valor is None:
        return "N/D"
    return f"{float(valor):.{casas}f}{sufixo}"


def _format_fundamental_data(registros: list[dict]) -> str:
    """Formata os registros fundamentalistas como texto estruturado para o prompt."""
    if not registros:
        return "Nenhum dado fundamentalista disponível no banco."

    linhas = []
    for r in registros:
        data = r["reference_date"]
        linhas.append(
            f"Data de referência: {data}\n"
            f"  P/L (Preço/Lucro):       {_fmt(r['pl_ratio'])}\n"
            f"  ROE (Retorno s/ PL):      {_fmt(r['roe'], '%', 2)}\n"
            f"  Dividend Yield:           {_fmt(r['dividend_yield'], '%', 2)}\n"
            f"  EV/EBITDA:                {_fmt(r['ev_ebitda'])}"
        )

        # Inclui campos extras do raw_data que possam existir
        raw = r.get("raw_data") or {}
        extras = {k: v for k, v in raw.items() if k not in {
            "pl_ratio", "roe", "dividend_yield", "ev_ebitda"
        }}
        if extras:
            extras_fmt = ", ".join(f"{k}: {v}" for k, v in list(extras.items())[:6])
            linhas.append(f"  Dados adicionais: {extras_fmt}")

    return "\n\n".join(linhas)


def _build_prompt(ticker: str, registros: list[dict]) -> str:
    """Monta o prompt completo com os dados fundamentalistas do ativo."""
    return f"""Ativo: {ticker} (Ação — B3)

=== DADOS FUNDAMENTALISTAS ===
{_format_fundamental_data(registros)}

Com base nos dados acima, gere uma análise fundamentalista completa e sua perspectiva \
sobre a qualidade do ativo para investimento."""


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
# 6.3.1 — Nó principal: fundamental_node
# ─────────────────────────────────────────────────────────────────────────────

def fundamental_node(state: "AgentState") -> "AgentState":
    """
    Nó LangGraph de análise fundamentalista.

    Executado APENAS para ativos do tipo 'STOCK'. Contratos futuros
    retornam imediatamente com `fundamental_analysis` vazio.

    Fluxo (apenas para STOCK):
        1. Verifica `asset_type` — se não for 'STOCK', retorna estado inalterado.
        2. Busca os últimos registros de FundamentalData do banco.
        3. Formata P/L, ROE, Dividend Yield e EV/EBITDA em contexto textual.
        4. Invoca o LLM para gerar a análise fundamentalista.
        5. Retorna o estado atualizado com `fundamental_analysis`.

    Em caso de erro (sem dados, LLM indisponível), retorna uma mensagem
    descritiva sem interromper o pipeline.

    Args:
        state: estado compartilhado do grafo (AgentState TypedDict).

    Returns:
        Estado atualizado com o campo `fundamental_analysis` preenchido.
        Para ativos FUTURE, retorna estado com `fundamental_analysis` vazio ("").
    """
    ticker     = state.get("ticker", "")
    asset_type = state.get("asset_type", "")

    # ── 1. Atalho para contratos futuros ──────────────────────────────────
    if asset_type != "STOCK":
        logger.info(
            "[fundamental_agent] Ativo %s do tipo '%s' — análise fundamentalista ignorada.",
            ticker, asset_type,
        )
        return {**state, "fundamental_analysis": ""}

    logger.info("[fundamental_agent] Iniciando análise fundamentalista para %s", ticker)

    # ── 2. Buscar dados do banco ───────────────────────────────────────────
    try:
        registros = _fetch_fundamental_data(ticker)
    except Exception as exc:  # noqa: BLE001
        logger.error("[fundamental_agent] Erro ao buscar FundamentalData: %s", exc)
        return {**state, "fundamental_analysis": f"Erro ao buscar dados fundamentalistas: {exc}"}

    # ── 3. Montar prompt ───────────────────────────────────────────────────
    prompt_usuario = _build_prompt(ticker, registros)

    # ── 4. Chamar LLM ─────────────────────────────────────────────────────
    try:
        llm = _get_llm()
        mensagens = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt_usuario),
        ]
        resposta = llm.invoke(mensagens)
        analise  = resposta.content
        logger.info("[fundamental_agent] Análise gerada com sucesso para %s", ticker)
    except Exception as exc:  # noqa: BLE001
        logger.error("[fundamental_agent] Erro ao chamar LLM: %s", exc)
        analise = f"Erro ao gerar análise fundamentalista via LLM: {exc}"

    # ── 5. Retornar estado atualizado ──────────────────────────────────────
    return {**state, "fundamental_analysis": analise}
