from django.apps import AppConfig


class AiAgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_agents'

    def ready(self):
        """
        Registra os signals do app ai_agents quando o Django termina de
        inicializar todos os apps.

        Tarefa: 6.6.3 — Registrar signal no ai_agents/apps.py.
        """
        from ai_agents.signals import _register_signals  # noqa: PLC0415
        _register_signals()
