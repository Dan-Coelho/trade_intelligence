# market_data/apps.py — AppConfig do app market_data
#
# Implementações:
#   4.6.2 — Registra os signals de market_data no método ready() do AppConfig,
#            garantindo que o Django ORM esteja totalmente inicializado antes
#            de conectar os handlers de signal.

from django.apps import AppConfig


class MarketDataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'market_data'
    verbose_name = 'Dados de Mercado'

    def ready(self):
        """
        Chamado pelo Django após o registro completo de todos os models.

        Importa e registra os signals definidos em market_data/signals.py.
        O método _register_signals() faz a importação das models de forma
        segura (post AppRegistry), evitando AppRegistryNotReady.
        """
        from .signals import _register_signals  # noqa: PLC0415
        _register_signals()
