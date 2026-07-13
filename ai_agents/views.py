# ai_agents/views.py — Views do app ai_agents
#
# Tarefa 7.2.2 — ChatView(LoginRequiredMixin, View):
#   Recebe `ticker` e `message` via POST, monta contexto com dados do banco,
#   chama LLM e retorna resposta via JsonResponse.

import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

logger = logging.getLogger(__name__)


class ChatView(LoginRequiredMixin, View):
    """
    Endpoint de Chat IA — responde perguntas sobre um ativo usando LLM + contexto do banco.

    Método: POST
    Payload JSON: { "ticker": "PETR4", "message": "Qual o sinal atual?" }

    Fluxo:
        1. Valida presença de `ticker` e `message`.
        2. Busca contexto do ativo no banco:
           - Último AISignal (sinal, confiança, síntese)
           - Último TechnicalIndicator (RSI, MACD)
           - Último FundamentalData (P/L, ROE) se disponível
           - Últimos 3 NewsArticle com sentiment
        3. Monta System Prompt + Human Message com o contexto.
        4. Chama LLM (Gemini via langchain_google_genai).
        5. Retorna { "reply": "..." } como JsonResponse.

    Em caso de erro, retorna { "reply": "Desculpe, não consegui processar..." }
    com status 200 para não quebrar o frontend HTMX.
    """

    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        # ── 1. Parse do payload ────────────────────────────────────────────────
        try:
            body   = json.loads(request.body)
            ticker  = str(body.get('ticker',  '')).strip().upper()
            message = str(body.get('message', '')).strip()
        except (json.JSONDecodeError, AttributeError):
            # Fallback para form-encoded (HTMX hx-include)
            ticker  = request.POST.get('ticker',  '').strip().upper()
            message = request.POST.get('message', '').strip()

        if not ticker or not message:
            return JsonResponse(
                {'reply': 'Por favor, informe o ticker e a mensagem.'},
                status=400,
            )

        logger.info(
            '[ChatView] Mensagem recebida — ticker=%s | user=%s | msg="%s"',
            ticker, request.user.username, message[:80],
        )

        # ── 2. Montar contexto do banco ────────────────────────────────────────
        context_lines = _build_context(ticker)

        # ── 3. Chamar LLM ──────────────────────────────────────────────────────
        reply = _call_llm(ticker, context_lines, message)

        return JsonResponse({'reply': reply})


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_context(ticker: str) -> list[str]:
    """
    Monta lista de linhas de contexto sobre o ativo para o LLM.

    Busca no banco:
        - AISignal mais recente
        - TechnicalIndicator mais recente (RSI + MACD)
        - FundamentalData mais recente (apenas STOCK)
        - Últimos 3 NewsArticle com sentiment

    Returns:
        Lista de strings com o contexto formatado.
    """
    lines: list[str] = []

    # ── AISignal ───────────────────────────────────────────────────────────────
    try:
        from ai_agents.models import AISignal          # noqa: PLC0415
        from market_data.models import Asset           # noqa: PLC0415

        asset   = Asset.objects.filter(ticker=ticker).first()
        signal  = (
            AISignal.objects
            .filter(asset=asset)
            .order_by('-generated_at')
            .first()
        ) if asset else None

        if signal:
            lines.append(
                f"Sinal IA atual: {signal.signal_type} "
                f"({signal.confidence_pct}% de confiança) — {signal.synthesis_text[:200]}"
            )
        else:
            lines.append("Sinal IA: ainda não gerado para este ativo.")
    except Exception as exc:  # noqa: BLE001
        logger.debug('[ChatView] Erro ao buscar AISignal: %s', exc)

    # ── TechnicalIndicator (RSI + MACD) ───────────────────────────────────────
    try:
        from analysis.models import TechnicalIndicator  # noqa: PLC0415

        if asset:
            rsi_row = (
                TechnicalIndicator.objects
                .filter(asset=asset, indicator_name='RSI')
                .order_by('-timestamp')
                .first()
            )
            macd_row = (
                TechnicalIndicator.objects
                .filter(asset=asset, indicator_name='MACD')
                .order_by('-timestamp')
                .first()
            )
            if rsi_row:
                rsi_val = rsi_row.values.get('rsi', '—')
                lines.append(f"RSI (14): {rsi_val}")
            if macd_row:
                macd_val = macd_row.values.get('macd', '—')
                hist_val = macd_row.values.get('hist', '—')
                lines.append(f"MACD: linha={macd_val}, histograma={hist_val}")
    except Exception as exc:  # noqa: BLE001
        logger.debug('[ChatView] Erro ao buscar TechnicalIndicator: %s', exc)

    # ── FundamentalData ────────────────────────────────────────────────────────
    try:
        from fundamentals.models import FundamentalData  # noqa: PLC0415

        if asset:
            fund = (
                FundamentalData.objects
                .filter(asset=asset)
                .order_by('-updated_at')
                .first()
            )
            if fund:
                lines.append(
                    f"Fundamentais: P/L={getattr(fund, 'p_l', '—')}, "
                    f"ROE={getattr(fund, 'roe', '—')}%, "
                    f"Div. Yield={getattr(fund, 'dividend_yield', '—')}%"
                )
    except Exception as exc:  # noqa: BLE001
        logger.debug('[ChatView] Erro ao buscar FundamentalData: %s', exc)

    # ── NewsArticle (últimas 3 notícias) ───────────────────────────────────────
    try:
        from news.models import NewsArticle  # noqa: PLC0415

        news_qs = (
            NewsArticle.objects
            .filter(tickers__icontains=ticker)
            .order_by('-published_at')[:3]
        )
        for article in news_qs:
            sentiment = getattr(article, 'sentiment', 'neutral')
            lines.append(f"Notícia ({sentiment}): {article.title[:120]}")
    except Exception as exc:  # noqa: BLE001
        logger.debug('[ChatView] Erro ao buscar NewsArticle: %s', exc)

    return lines


_SYSTEM_PROMPT = """\
Você é um assistente financeiro especialista no mercado financeiro brasileiro.
Responda de forma clara, objetiva e profissional, em português.
Use o contexto de mercado fornecido para embasar suas respostas.
Seja direto — respostas com no máximo 150 palavras, salvo quando solicitado mais detalhes.
Nunca faça recomendações de compra/venda — apenas análise informativa.
"""


def _call_llm(ticker: str, context_lines: list[str], message: str) -> str:
    """
    Chama o LLM (Gemini) com o contexto do ativo e a pergunta do usuário.

    Args:
        ticker:        código do ativo.
        context_lines: linhas de contexto do banco (sinal, indicadores, news).
        message:       pergunta do usuário.

    Returns:
        Texto da resposta do LLM (str).
    """
    from django.conf import settings                          # noqa: PLC0415
    from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415

    context_block = '\n'.join(context_lines) if context_lines else 'Sem contexto disponível.'
    human_content = (
        f"Ativo analisado: {ticker}\n\n"
        f"Contexto de mercado:\n{context_block}\n\n"
        f"Pergunta: {message}"
    )

    try:
        api_key = getattr(settings, 'LLM_API_KEY', '')
        model   = getattr(settings, 'LLM_MODEL', 'gemini-1.5-flash')
        llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=0.4,
        )
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ])
        return str(response.content).strip()
    except Exception as exc:  # noqa: BLE001
        logger.error('[ChatView] Erro ao chamar LLM: %s', exc)
        return (
            'Desculpe, não consegui processar sua pergunta no momento. '
            'Tente novamente em instantes.'
        )
