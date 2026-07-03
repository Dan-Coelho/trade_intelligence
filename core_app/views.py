# core_app/views.py — Views do app core (Landing Page pública)
# Tarefa 1.3 — Landing Page Pública

from django.shortcuts import redirect
from django.views.generic import TemplateView


class LandingPageView(TemplateView):
    """
    View pública da landing page.
    Redireciona usuários autenticados diretamente para o dashboard.
    """
    # 1.3.1 — CBV usando TemplateView
    template_name = 'core_app/landing.html'

    def dispatch(self, request, *args, **kwargs):
        # 1.3.2 — Redirecionamento para o dashboard se já estiver logado
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        return super().dispatch(request, *args, **kwargs)
