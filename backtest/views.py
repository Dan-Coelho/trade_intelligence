# backtest/views.py — Views do app backtest
#
# Tarefas:
#   7.3.2 — BacktestView(LoginRequiredMixin, FormView): exibe formulário e
#            dispara task run_backtest.delay() no form_valid()
#   7.3.4 — BacktestResultView(LoginRequiredMixin, DetailView): exibe resultado
#            com Win Rate, Sharpe e Drawdown

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import DetailView, FormView

from backtest.forms import BacktestForm
from backtest.models import BacktestResult

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 7.3.2 — BacktestView
# ─────────────────────────────────────────────────────────────────────────────

class BacktestView(LoginRequiredMixin, FormView):
    """
    Exibe o formulário de configuração de backtest e dispara a task Celery
    ao submeter o formulário com dados válidos.

    GET  /backtest/          → renderiza form.html
    POST /backtest/          → valida form, dispara run_backtest.delay(),
                               retorna JSON { task_id, result_url } para o frontend

    O formulário usa HTMX (hx-post) — a resposta JSON é processada pelo JS/Alpine
    que redireciona o usuário para a página de resultado quando a task terminar.
    """

    form_class    = BacktestForm
    template_name = 'backtest/form.html'
    success_url   = reverse_lazy('backtest:run')

    def get_initial(self):
        """Pré-preenche o ticker via query param (ex.: ?ticker=PETR4)."""
        initial = super().get_initial()
        ticker  = self.request.GET.get('ticker', '')
        if ticker:
            initial['ticker'] = ticker.upper()
        return initial

    def form_valid(self, form):
        """
        Dispara task Celery run_backtest com os dados validados.

        Retorna JsonResponse com task_id e URL de polling/resultado,
        compatível com requisições HTMX e fetch do frontend.
        """
        from backtest.tasks import run_backtest  # noqa: PLC0415

        data = form.cleaned_data
        task = run_backtest.delay(
            user_id    = self.request.user.pk,
            ticker     = data['ticker'].upper(),
            start_date = str(data['start_date']),
            end_date   = str(data['end_date']),
            strategy   = data['strategy'],
            capital    = float(data['initial_capital']),
        )

        logger.info(
            '[BacktestView] Task disparada — user=%s | ticker=%s | strategy=%s | task_id=%s',
            self.request.user.username,
            data['ticker'],
            data['strategy'],
            task.id,
        )

        return JsonResponse({
            'status':   'queued',
            'task_id':  task.id,
            'message':  (
                f"Backtest de {data['ticker']} ({data['strategy']}) em andamento. "
                "Aguarde o resultado..."
            ),
            'poll_url': f'/backtest/status/{task.id}/',
        })

    def form_invalid(self, form):
        """Retorna erros de validação como JSON para o frontend HTMX."""
        if self.request.headers.get('HX-Request'):
            errors = {
                field: [str(e) for e in errs]
                for field, errs in form.errors.items()
            }
            return JsonResponse({'status': 'error', 'errors': errors}, status=422)
        return super().form_invalid(form)


# ─────────────────────────────────────────────────────────────────────────────
# 7.3.4 — BacktestResultView
# ─────────────────────────────────────────────────────────────────────────────

class BacktestResultView(LoginRequiredMixin, DetailView):
    """
    Exibe o resultado de um backtest com Win Rate, Sharpe e Drawdown.

    GET /backtest/result/<pk>/  → renderiza result.html

    Contexto extra disponível no template:
        - return_pct:   retorno total em percentual.
        - profit:       lucro/prejuízo absoluto em R$.
        - trades_count: número total de trades.
        - winners:      número de trades com PnL positivo.
        - losers:       número de trades com PnL negativo.
    """

    model               = BacktestResult
    template_name       = 'backtest/result.html'
    context_object_name = 'result'

    def get_queryset(self):
        """Garante que o usuário só vê seus próprios backtests."""
        return BacktestResult.objects.filter(user=self.request.user).select_related('asset')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        result  = self.object

        initial = float(result.initial_capital)
        final   = float(result.final_capital)

        context['profit']       = round(final - initial, 2)
        context['return_pct']   = round(((final / initial) - 1) * 100, 2) if initial else 0
        context['trades_count'] = len(result.trades_log)
        context['winners']      = sum(1 for t in result.trades_log if t.get('pnl', 0) > 0)
        context['losers']       = sum(1 for t in result.trades_log if t.get('pnl', 0) <= 0)

        return context


# ─────────────────────────────────────────────────────────────────────────────
# View de status da task Celery (polling HTMX)
# ─────────────────────────────────────────────────────────────────────────────

class BacktestStatusView(LoginRequiredMixin, DetailView):
    """
    Polling endpoint para verificar o status de uma task run_backtest.

    GET /backtest/status/<task_id>/
    Retorna JSON:
        { status: 'pending'|'success'|'failure', result_url: '...' }

    O frontend faz polling a cada 2s via HTMX ou fetch até o status ser
    'success' ou 'failure', então redireciona para result_url.
    """

    http_method_names = ['get']

    def get(self, request, *args, **kwargs):
        from celery.result import AsyncResult  # noqa: PLC0415

        task_id = kwargs.get('task_id', '')
        result  = AsyncResult(task_id)

        if result.state == 'SUCCESS' and isinstance(result.result, dict):
            res_id   = result.result.get('result_id')
            # Verifica que o resultado pertence ao usuário
            if res_id:
                bt = BacktestResult.objects.filter(pk=res_id, user=request.user).first()
                if bt:
                    return JsonResponse({
                        'status':     'success',
                        'result_url': f'/backtest/result/{res_id}/',
                    })
            return JsonResponse({'status': 'success', 'result_url': '/backtest/'})

        if result.state == 'FAILURE':
            return JsonResponse({'status': 'failure', 'error': str(result.result)})

        return JsonResponse({'status': 'pending'})
