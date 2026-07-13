# dashboard/routing.py — Roteamento WebSocket do app dashboard
#
# Tarefa 7.1.4 — websocket_urlpatterns mapeando ws/asset/<ticker>/

from django.urls import re_path

from dashboard import consumers

# Lista de padrões de URL para conexões WebSocket.
# Importada pelo core/asgi.py e inserida no URLRouter.
websocket_urlpatterns = [
    # ws://host/ws/asset/PETR4/  →  AssetConsumer
    # ticker: letras maiúsculas/minúsculas, dígitos e hífen (ex.: PETR4, WINM25, BTC-USD)
    re_path(r'^ws/asset/(?P<ticker>[A-Za-z0-9\-]+)/$', consumers.AssetConsumer.as_asgi()),
]
