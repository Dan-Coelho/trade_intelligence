# watchlist/views.py — Views do app watchlist
#
# Tarefas:
#   7.4.2 — WatchlistAddView(LoginRequiredMixin, View): POST ticker → cria Watchlist entry → partial HTMX
#   7.4.3 — WatchlistRemoveView(LoginRequiredMixin, View): POST asset_id → remove entry → partial HTMX
#   7.4.4 — AlertCreateView(LoginRequiredMixin, CreateView): cria PriceAlert via PriceAlertForm
#   + AlertListView, AlertDeleteView

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView

from market_data.models import Asset
from watchlist.forms import PriceAlertForm
from watchlist.models import PriceAlert, Watchlist

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 7.4.2 — WatchlistAddView
# ─────────────────────────────────────────────────────────────────────────────

class WatchlistAddView(LoginRequiredMixin, View):
    """
    Adiciona um ativo à watchlist do usuário autenticado.

    POST /watchlist/add/
    Body (form-encoded): ticker=PETR4

    Retorna o partial HTML #watchlist-items atualizado para o HTMX
    substituir a sidebar sem recarregar a página.
    Também aceita requisições JSON retornando { status, message }.
    """

    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        ticker = request.POST.get('ticker', '').strip().upper()

        if not ticker:
            return HttpResponse('<p class="text-xs text-red-400 px-3 py-2">Ticker não informado.</p>', status=400)

        try:
            asset = Asset.objects.get(ticker=ticker)
        except Asset.DoesNotExist:
            return HttpResponse(
                f'<p class="text-xs text-red-400 px-3 py-2">Ativo "{ticker}" não encontrado.</p>',
                status=404,
            )

        wl_item, created = Watchlist.objects.get_or_create(
            user  = request.user,
            asset = asset,
        )

        if created:
            logger.info('[WatchlistAdd] %s adicionado à watchlist de %s.', ticker, request.user.email)
        else:
            logger.debug('[WatchlistAdd] %s já está na watchlist de %s.', ticker, request.user.email)

        # Retorna partial HTML atualizado para HTMX
        return self._render_partial(request)

    def _render_partial(self, request):
        """Renderiza o partial da sidebar com a watchlist atualizada."""
        watchlist = (
            Watchlist.objects
            .filter(user=request.user)
            .select_related('asset')
            .order_by('display_order', 'asset__ticker')
        )
        return render(
            request,
            'watchlist/partials/watchlist_items.html',
            {'watchlist': watchlist},
        )


# ─────────────────────────────────────────────────────────────────────────────
# 7.4.3 — WatchlistRemoveView
# ─────────────────────────────────────────────────────────────────────────────

class WatchlistRemoveView(LoginRequiredMixin, View):
    """
    Remove um ativo da watchlist do usuário autenticado.

    POST /watchlist/remove/<asset_id>/
    Sem body adicional — o asset_id vem da URL.

    Retorna o partial HTML #watchlist-items atualizado para o HTMX.
    """

    http_method_names = ['post']

    def post(self, request, asset_id, *args, **kwargs):
        deleted, _ = Watchlist.objects.filter(
            user=request.user,
            asset_id=asset_id,
        ).delete()

        if deleted:
            logger.info('[WatchlistRemove] asset_id=%d removido da watchlist de %s.', asset_id, request.user.email)

        # Retorna partial atualizado para HTMX
        watchlist = (
            Watchlist.objects
            .filter(user=request.user)
            .select_related('asset')
            .order_by('display_order', 'asset__ticker')
        )
        return render(
            request,
            'watchlist/partials/watchlist_items.html',
            {'watchlist': watchlist},
        )


# ─────────────────────────────────────────────────────────────────────────────
# 7.4.4 — AlertCreateView
# ─────────────────────────────────────────────────────────────────────────────

class AlertCreateView(LoginRequiredMixin, CreateView):
    """
    Cria um alerta de preço para um ativo da watchlist.

    GET  /watchlist/alerts/add/?ticker=PETR4  → exibe formulário
    POST /watchlist/alerts/add/?ticker=PETR4  → cria alerta, redireciona para lista

    O `asset` é obtido via query param `ticker`.
    O `user` é preenchido automaticamente com o usuário autenticado.
    """

    model         = PriceAlert
    form_class    = PriceAlertForm
    template_name = 'watchlist/alert_form.html'
    success_url   = reverse_lazy('watchlist:alert_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ticker'] = self.request.GET.get('ticker', '').upper()
        return context

    def form_valid(self, form):
        ticker = self.request.GET.get('ticker', '').upper()
        asset  = get_object_or_404(Asset, ticker=ticker)

        form.instance.user  = self.request.user
        form.instance.asset = asset

        logger.info(
            '[AlertCreate] Alerta criado — user=%s | %s %s R$ %s',
            self.request.user.email,
            ticker,
            form.instance.get_condition_display(),
            form.instance.target_price,
        )
        return super().form_valid(form)


# ─────────────────────────────────────────────────────────────────────────────
# AlertListView — lista de alertas do usuário
# ─────────────────────────────────────────────────────────────────────────────

class AlertListView(LoginRequiredMixin, ListView):
    """
    Exibe a lista de alertas de preço do usuário autenticado.

    GET /watchlist/alerts/
    """

    model               = PriceAlert
    template_name       = 'watchlist/alert_list.html'
    context_object_name = 'alerts'
    paginate_by         = 20

    def get_queryset(self):
        return (
            PriceAlert.objects
            .filter(user=self.request.user)
            .select_related('asset')
            .order_by('-created_at')
        )


# ─────────────────────────────────────────────────────────────────────────────
# AlertDeleteView — desativa/exclui um alerta
# ─────────────────────────────────────────────────────────────────────────────

class AlertDeleteView(LoginRequiredMixin, View):
    """
    Desativa (soft-delete via is_active=False) ou remove permanentemente um alerta.

    POST /watchlist/alerts/<pk>/delete/
    Retorna JSON { status } ou redireciona para a lista.
    """

    http_method_names = ['post']

    def post(self, request, pk, *args, **kwargs):
        alert = get_object_or_404(PriceAlert, pk=pk, user=request.user)
        alert.delete()
        logger.info('[AlertDelete] Alerta id=%d excluído — user=%s.', pk, request.user.email)

        if request.headers.get('HX-Request'):
            return HttpResponse(status=200)   # HTMX remove o elemento do DOM
        return JsonResponse({'status': 'deleted'})
