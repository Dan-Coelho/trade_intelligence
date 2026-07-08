# core/celery.py — Configuração padrão do Celery para o projeto Django
# Tarefa 4.1.1

import os

from celery import Celery

# Define o módulo de settings padrão do Django para o Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('trade_intelligence')

# Lê as configurações do Django prefixadas com CELERY_
# Exemplo: CELERY_BROKER_URL → app.conf.broker_url
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descobre automaticamente tasks em todos os apps instalados
# Procura por arquivos tasks.py em cada app do INSTALLED_APPS
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Task de diagnóstico — imprime a request atual (útil para debug)."""
    print(f'Request: {self.request!r}')
