"""
ai_agents/agents/macro_agent.py

Nó de análise macroeconômica e sentimento de notícias do grafo LangGraph.

Responsabilidade:
    - Buscar os indicadores macroeconômicos mais recentes do banco:
      SELIC, IPCA e quaisquer outros MacroIndicator disponíveis.
    - Buscar os últimos NewsArticle associados ao ticker com seu sentiment
      já classificado (BULLISH/BEARISH/NEUTRAL).
    - Formatar o contexto combinado em texto estruturado.
    - Chamar o LLM (Google Gemini via langchain-google-genai) para gerar
      uma análise macro/notícias em linguagem natural.
    - Retornar o estado atualizado com o campo `macro_analysis`.

Tarefa: 6.4.1
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

_MAX_MACRO_PER_INDICATOR = 3   # Últimos N registros por indicador macro
_MAX_NEWS = 10                 # Últimas N notícias do ticker a incluir
_LLM_MODEL = "gemini-1.5-flash"
_LLM_TEMPERATURE = 0.3

# Indicadores macro prioritários (ordem de exibição no prompt)
_MACRO_PRIORITY = ["SELIC", "IPCA", "PIB", "USD/BRL", "DOLAR", "CAMBIO"]

SYSTEM_PROMPT = """Você é um analista macroeconômico especializado no mercado financeiro brasileiro.
Sua função é interpretar o cenário macro (SELIC, IPCA, PIB, câmbio) e o fluxo de
notícias recentes de um ativo para gerar um parecer sobre o ambiente externo que
afeta aquele ativo.

Regras:
- Cite os valores dos indicadores macro e suas tendências recentes.
- Analise o sentimento geral das notícias (majoritariamente positivo, negativo ou misto).
- Mencione os títulos de notícias mais relevantes com seu impacto esperado.
- Avalie como o cenário macro atual favorece ou prejudica o ativo.
- Conclua com uma perspectiva macro (Favorável, Desfavorável ou Neutro) com justificativa.
- Responda sempre em português brasileiro.
- Seja conciso: máximo de 350 palavras.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de busca no banco de dados
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_macro_indicators() -> dict[str, list[dict]]:
    """
    Busca os últimos registros de MacroIndicator agrupados por nome.

    Retorna um dicionário {nome_indicador: [lista_de_registros]}.
    Os indicadores prioritários (SELIC, IPCA, PIB) aparecem primeiro.
    """
    from news.models import MacroIndicator  # noqa: PLC0415

    # Busca todos os indicadores disponíveis
    todos = (
        MacroIndicator.objects
        .order_by("name", "-reference_date")
        .values("name", "reference_date", "value", "unit", "source")
    )

    # Agrupa por nome, mantendo os últimos N por indicador
    agrupados: dict[str, list[dict]] = {}
    for registro in todos:
        nome = registro["name"]
        if nome not in agrupados:
            agrupados[nome] = []
        if len(agrupados[nome]) < _MAX_MACRO_PER_INDICATOR:
            agrupados[nome].append(registro)

    # Reordena: prioritários primeiro, depois alfabético
    def ordem(nome: str) -> tuple:
        try:
            idx = _MACRO_PRIORITY.index(nome.upper())
        except ValueError:
            idx = len(_MACRO_PRIORITY)
        return (idx, nome)

    return dict(sorted(agrupados.items(), key=lambda kv: ordem(kv[0])))


def _fetch_news(ticker: str) -> list[dict]:
    """
    Busca as últimas notícias associadas ao ticker com seu sentimento classificado.

    Inclui tanto notícias diretamente vinculadas ao asset quanto notícias gerais
    (asset=None) para contextualização macroeconômica.
    """
    from news.models import NewsArticle  # noqa: PLC0415

    # Notícias específicas do ativo
    noticias_ativo = (
        NewsArticle.objects
        .filter(asset__ticker=ticker)
        .order_by("-published_at")
        .values("title", "source_name", "sentiment", "sentiment_score", "published_at")
        [:_MAX_NEWS]
    )

    resultado = list(noticias_ativo)

    # Complementa com notícias gerais se houver menos que o mínimo desejado
    if len(resultado) < 5:
        noticias_gerais = (
            NewsArticle.objects
            .filter(asset__isnull=True)
            .order_by("-published_at")
            .values("title", "source_name", "sentiment", "sentiment_score", "published_at")
            [: _MAX_NEWS - len(resultado)]
        )
        resultado += list(noticias_gerais)

    return resultado


# ─────────────────────────────────────────────────────────────────────────────
# Formatação do contexto para o LLM
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_valor(valor, casas: int = 4) -> str:
    """Formata um Decimal/None para exibição."""
    if valor is None:
        return "N/D"
    return f"{float(valor):.{casas}f}"


def _format_macro(indicadores: dict[str, list[dict]]) -> str:
    """Formata os indicadores macroeconômicos como texto estruturado."""
    if not indicadores:
        return "Nenhum indicador macroeconômico disponível no banco."

    blocos = []
    for nome, registros in indicadores.items():
        unidade = registros[0]["unit"] if registros else ""
        valores = " → ".join(
            f"{r['reference_date']}: {_fmt_valor(r['value'])} {unidade}"
            for r in registros
        )
        blocos.append(f"{nome} ({registros[0]['source']}): {valores}")

    return "\n".join(blocos)


def _sentimento_emoji(sentiment: str) -> str:
    return {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "🟡"}.get(sentiment, "⚪")


def _format_news(noticias: list[dict]) -> str:
    """Formata as notícias como lista estruturada para o prompt."""
    if not noticias:
        return "Nenhuma notícia recente encontrada para este ativo."

    linhas = []
    for n in noticias:
        emoji = _sentimento_emoji(n["sentiment"])
        score = n.get("sentiment_score")
        score_txt = f" (score: {_fmt_valor(score, 3)})" if score is not None else ""
        data = str(n["published_at"])[:16]
        linhas.append(
            f"{emoji} [{n['source_name']} — {data}]{score_txt}\n"
            f"   \"{n['title']}\""
        )

    # Sumariza sentimentos
    contagem = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
    for n in noticias:
        contagem[n.get("sentiment", "NEUTRAL")] = contagem.get(n.get("sentiment", "NEUTRAL"), 0) + 1

    resumo = (
        f"Resumo de sentimento: 🟢 {contagem['BULLISH']} alta | "
        f"🔴 {contagem['BEARISH']} baixa | 🟡 {contagem['NEUTRAL']} neutro"
    )

    return resumo + "\n\n" + "\n".join(linhas)


def _build_prompt(ticker: str, macro: dict[str, list[dict]], noticias: list[dict]) -> str:
    """Monta o prompt completo com cenário macro e notícias do ativo."""
    return f"""Ativo analisado: {ticker}

=== INDICADORES MACROECONÔMICOS ===
{_format_macro(macro)}

=== NOTÍCIAS RECENTES ===
{_format_news(noticias)}

Com base no cenário macroeconômico e no fluxo de notícias acima, gere uma análise \
do ambiente externo e seu impacto esperado no ativo {ticker}."""


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
# 6.4.1 — Nó principal: macro_node
# ─────────────────────────────────────────────────────────────────────────────

def macro_node(state: "AgentState") -> "AgentState":
    """
    Nó LangGraph de análise macroeconômica e sentimento de notícias.

    Executado para todos os tipos de ativo (STOCK e FUTURE), pois o contexto
    macro e as notícias são relevantes em ambos os casos.

    Fluxo:
        1. Extrai `ticker` do estado compartilhado.
        2. Busca MacroIndicator (SELIC, IPCA, PIB, etc.) do banco.
        3. Busca NewsArticle com sentiment para o ticker (e gerais como fallback).
        4. Formata indicadores e notícias em contexto textual estruturado.
        5. Invoca o LLM para gerar a análise macro/notícias.
        6. Retorna o estado atualizado com `macro_analysis`.

    Em caso de erro (sem dados, LLM indisponível), retorna uma mensagem
    descritiva sem interromper o pipeline.

    Args:
        state: estado compartilhado do grafo (AgentState TypedDict).

    Returns:
        Estado atualizado com o campo `macro_analysis` preenchido.
    """
    ticker = state.get("ticker", "")
    logger.info("[macro_agent] Iniciando análise macro/notícias para %s", ticker)

    # ── 1. Buscar dados do banco ───────────────────────────────────────────
    try:
        indicadores_macro = _fetch_macro_indicators()
        noticias          = _fetch_news(ticker)
    except Exception as exc:  # noqa: BLE001
        logger.error("[macro_agent] Erro ao buscar dados do banco: %s", exc)
        return {**state, "macro_analysis": f"Erro ao buscar dados macro/notícias: {exc}"}

    # ── 2. Montar prompt ───────────────────────────────────────────────────
    prompt_usuario = _build_prompt(ticker, indicadores_macro, noticias)

    # ── 3. Chamar LLM ─────────────────────────────────────────────────────
    try:
        llm = _get_llm()
        mensagens = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=prompt_usuario),
        ]
        resposta = llm.invoke(mensagens)
        analise  = resposta.content
        logger.info("[macro_agent] Análise gerada com sucesso para %s", ticker)
    except Exception as exc:  # noqa: BLE001
        logger.error("[macro_agent] Erro ao chamar LLM: %s", exc)
        analise = f"Erro ao gerar análise macro/notícias via LLM: {exc}"

    # ── 4. Retornar estado atualizado ──────────────────────────────────────
    return {**state, "macro_analysis": analise}
