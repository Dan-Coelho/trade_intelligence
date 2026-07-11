"""
ai_agents/graph.py

Define o StateGraph LangGraph para o sistema multi-agente de análise de ativos.

Fluxo geral:
  [entrada] → supervisor_node → technical_node  ─┐
                              → fundamental_node  ├→ synthesis_node → [saída: AISignal]
                              → macro_node       ─┘

Tarefas:
  6.1.2 — StateGraph
  6.1.3 — AgentState
  6.5.1 — supervisor_node / route_agents (wired aqui)
  6.5.2 — synthesis_node (wired aqui)
"""

from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict

from langgraph.graph import END, START, StateGraph


# ─────────────────────────────────────────────────────────────────────────────
# 6.1.3 — Estado compartilhado entre todos os agentes do grafo
# ─────────────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """Estado compartilhado trafegado entre os nós do grafo LangGraph.

    Campos:
        ticker              — Código do ativo (ex.: "PETR4", "WINM25").
        asset_type          — Tipo de ativo: "STOCK" ou "FUTURE".
        technical_analysis  — Análise técnica gerada pelo TechnicalAgent.
        fundamental_analysis— Análise fundamentalista gerada pelo FundamentalAgent
                              (vazio para contratos futuros).
        macro_analysis      — Análise macro/notícias gerada pelo MacroAgent.
        signal              — Sinal consolidado: "BULLISH", "BEARISH" ou "NEUTRAL".
        confidence          — Confiança do sinal em percentual (0–100).
        synthesis           — Texto de síntese gerado pelo SynthesisAgent.
    """

    ticker: str
    asset_type: str                         # "STOCK" | "FUTURE"
    technical_analysis: Optional[str]
    fundamental_analysis: Optional[str]
    macro_analysis: Optional[str]
    signal: Optional[str]                   # "BULLISH" | "BEARISH" | "NEUTRAL"
    confidence: Optional[float]             # 0.0 – 100.0
    synthesis: Optional[str]


# ─────────────────────────────────────────────────────────────────────────────
# 6.1.2 / 6.5 — Definição do StateGraph com todos os nós reais
# ─────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Constrói e compila o grafo multi-agente completo.

    Estrutura de nós (todos implementados):
        supervisor_node → normaliza estado e prepara roteamento     [6.5.1]
        technical_node  → análise técnica (RSI, MACD, padrões)      [6.2.1]
        fundamental_node→ análise fundamentalista (apenas STOCK)    [6.3.1]
        macro_node      → análise macro e sentimento de notícias    [6.4.1]
        synthesis_node  → consolida análises e emite sinal final    [6.5.2]

    Roteamento:
        STOCK  → technical_node + fundamental_node + macro_node (paralelo)
        FUTURE → technical_node + macro_node (paralelo)

    Os três nós de análise convergem para synthesis_node antes do END.
    """
    # Importações locais — evita problemas de importação circular e de
    # inicialização do Django ORM antes do setup (apps.ready)
    from ai_agents.agents.technical_agent   import technical_node    # noqa: PLC0415
    from ai_agents.agents.fundamental_agent import fundamental_node  # noqa: PLC0415
    from ai_agents.agents.macro_agent       import macro_node        # noqa: PLC0415
    from ai_agents.agents.supervisor        import supervisor_node, route_agents  # noqa: PLC0415
    from ai_agents.agents.synthesis         import synthesis_node    # noqa: PLC0415

    graph = StateGraph(AgentState)

    # ── Registrar nós ──────────────────────────────────────────────────────
    graph.add_node("supervisor",      supervisor_node)  # 6.5.1
    graph.add_node("technical_node",  technical_node)   # 6.2.1
    graph.add_node("fundamental_node", fundamental_node) # 6.3.1
    graph.add_node("macro_node",      macro_node)       # 6.4.1
    graph.add_node("synthesis_node",  synthesis_node)   # 6.5.2

    # ── Aresta de entrada ──────────────────────────────────────────────────
    graph.add_edge(START, "supervisor")

    # ── Roteamento condicional do supervisor ───────────────────────────────
    # route_agents() retorna [technical_node, macro_node] para FUTURE
    # ou [technical_node, fundamental_node, macro_node] para STOCK
    graph.add_conditional_edges(
        "supervisor",
        route_agents,
        ["technical_node", "fundamental_node", "macro_node"],
    )

    # ── Convergência para a síntese ────────────────────────────────────────
    graph.add_edge("technical_node",   "synthesis_node")
    graph.add_edge("fundamental_node", "synthesis_node")
    graph.add_edge("macro_node",       "synthesis_node")

    # ── Finalização ────────────────────────────────────────────────────────
    graph.add_edge("synthesis_node", END)

    return graph


# ── Instância compilada (importável pelos outros módulos) ──────────────────
#   Uso: from ai_agents.graph import compiled_graph
#        result = compiled_graph.invoke(initial_state)
compiled_graph = build_graph().compile()
