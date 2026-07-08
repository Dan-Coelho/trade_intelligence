# core/__init__.py
# Tarefa 4.1.2 — Importa o app Celery para que o auto-discover funcione
# quando o Django inicializa, garantindo que tasks sejam registradas corretamente.

from .celery import app as celery_app

__all__ = ('celery_app',)
