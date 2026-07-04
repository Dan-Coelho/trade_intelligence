# dashboard/views.py — Views do app Dashboard
# Tarefa 1.4.1 — LoginRequiredMixin aplicado como padrão nas CBVs do dashboard
# Tarefa 3.1.1 — DashboardView com context de watchlist do usuário logado

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from watchlist.models import Watchlist


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    View principal do dashboard.

    Utiliza LoginRequiredMixin para garantir que apenas usuários autenticados
    acessem esta view. Usuários não autenticados são redirecionados para
    /accounts/login/ automaticamente (conforme LOGIN_URL padrão do Django).

    Este padrão de herança (LoginRequiredMixin, TemplateView) será replicado
    em TODAS as CBVs das sprints seguintes, conforme tarefa 1.4.1.

    Contexto disponível no template:
        - watchlist: QuerySet com os itens da watchlist do usuário logado,
          ordenados por display_order e ticker do ativo.
        - user: instância do usuário autenticado.
    """
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        # 3.1.1 — Watchlist do usuário logado com select_related para evitar N+1
        context['watchlist'] = (
            Watchlist.objects
            .filter(user=self.request.user)
            .select_related('asset')
            .order_by('display_order', 'asset__ticker')
        )
        # 3.2.4 — Lista de timeframes para o seletor do gráfico
        context['timeframes'] = ['1m', '5m', '15m', '1h', '1D']
        # Ticker pré-selecionado via query param (opcional)
        context['selected_ticker'] = self.request.GET.get('ticker', '')
        return context
