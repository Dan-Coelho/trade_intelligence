from django.apps import AppConfig


class WatchlistConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'watchlist'

    def ready(self):
        # 7.4.6 — Registra signal post_save do PriceAlert para log de auditoria
        from watchlist.signals import _register_signals  # noqa: PLC0415
        _register_signals()
