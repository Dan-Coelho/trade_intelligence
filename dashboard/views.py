# dashboard/views.py — Views do app Dashboard
# Tarefa 1.4.1 — LoginRequiredMixin aplicado como padrão nas CBVs do dashboard

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    View principal do dashboard.

    Utiliza LoginRequiredMixin para garantir que apenas usuários autenticados
    acessem esta view. Usuários não autenticados são redirecionados para
    /accounts/login/ automaticamente (conforme LOGIN_URL padrão do Django).

    Este padrão de herança (LoginRequiredMixin, TemplateView) será replicado
    em TODAS as CBVs das sprints seguintes, conforme tarefa 1.4.1.
    """
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Placeholder — watchlist será populada na Sprint 3
        context['user'] = self.request.user
        return context
