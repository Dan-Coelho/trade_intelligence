"""
ai_agents/agents/supervisor.py

Nó supervisor do grafo LangGraph.

Responsabilidade:
    - Inspecionar o campo `asset_type` do estado compartilhado.
    - Decidir quais nós de análise devem ser acionados em seguida:
        * STOCK  → technical_node + fundamental_node + macro_node (paralelo)
        * FUTURE → technical_node + macro_node (paralelo, sem fundamentalista)
    - Esta lógica é exposta como a função de roteamento condicional
      `route_agents(state)` que é passada a `add_conditional_edges()` no grafo.

Tarefa: 6.5.1
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_agents.graph import AgentState

logger = logging.getLogger(__name__)

# Nós de análise disponíveis no grafo
_NODE_TECHNICAL    = "technical_node"
_NODE_FUNDAMENTAL  = "fundamental_node"
_NODE_MACRO        = "macro_node"


def supervisor_node(state: "AgentState") -> "AgentState":
    """
    Nó supervisor: valida e prepara o estado antes do roteamento.

    Não modifica o estado — apenas loga o início do pipeline e
    garante que campos opcionais estejam inicializados como None
    para evitar KeyError nos nós seguintes.

    Args:
        state: estado compartilhado do grafo (AgentState TypedDict).

    Returns:
        Estado com campos opcionais garantidamente inicializados.
    """
    ticker     = state.get("ticker", "")
    asset_type = state.get("asset_type", "STOCK")

    logger.info(
        "[supervisor] Iniciando pipeline para %s (tipo: %s)",
        ticker, asset_type,
    )

    # Garante que todos os campos opcionais existam no estado
    return {
        **state,
        "ticker":               ticker,
        "asset_type":           asset_type.upper(),
        "technical_analysis":   state.get("technical_analysis"),
        "fundamental_analysis": state.get("fundamental_analysis"),
        "macro_analysis":       state.get("macro_analysis"),
        "signal":               state.get("signal"),
        "confidence":           state.get("confidence"),
        "synthesis":            state.get("synthesis"),
    }


def route_agents(state: "AgentState") -> list[str]:
    """
    Função de roteamento condicional do supervisor.

    Decide quais nós de análise devem ser executados em paralelo
    com base no tipo do ativo:

        STOCK  → [technical_node, fundamental_node, macro_node]
        FUTURE → [technical_node, macro_node]
        outros → [technical_node, macro_node]  (fallback conservador)

    Esta função é passada como segundo argumento de
    `graph.add_conditional_edges("supervisor", route_agents, [...])`.

    Args:
        state: estado compartilhado do grafo.

    Returns:
        Lista com os nomes dos nós a acionar em seguida.
    """
    asset_type = state.get("asset_type", "").upper()
    ticker     = state.get("ticker", "")

    if asset_type == "STOCK":
        nos = [_NODE_TECHNICAL, _NODE_FUNDAMENTAL, _NODE_MACRO]
        logger.info(
            "[supervisor] %s (STOCK) → acionando: %s",
            ticker, ", ".join(nos),
        )
    else:
        nos = [_NODE_TECHNICAL, _NODE_MACRO]
        logger.info(
            "[supervisor] %s (%s) → acionando: %s (sem fundamentalista)",
            ticker, asset_type or "FUTURE", ", ".join(nos),
        )

    return nos
