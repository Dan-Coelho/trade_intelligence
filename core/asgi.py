"""
core/asgi.py

Configuração ASGI do projeto com suporte a HTTP e WebSocket via Django Channels.

Tarefa 7.1.2 — URLRouter para WebSocket com roteamento do dashboard.

Fluxo de roteamento:
    ws://host/ws/asset/<ticker>/  →  dashboard.consumers.AssetConsumer
    http://host/...               →  Django WSGI/HTTP application padrão
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Inicializa o Django antes de qualquer import que dependa do ORM/apps
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack          # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from dashboard.routing import websocket_urlpatterns     # noqa: E402

application = ProtocolTypeRouter(
    {
        # Requisições HTTP padrão — delegadas ao Django ASGI app
        'http': django_asgi_app,

        # Conexões WebSocket — roteadas pelo URLRouter do dashboard
        # AllowedHostsOriginValidator garante que somente origens listadas
        # em ALLOWED_HOSTS possam estabelecer conexão WebSocket.
        'websocket': AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns)
            )
        ),
    }
)
