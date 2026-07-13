# dashboard/consumers.py — Consumer WebSocket do app dashboard
#
# Tarefa 7.1.3 — AsyncWebsocketConsumer AssetConsumer:
#   - join/leave grupo do ticker
#   - receber e enviar mensagens de sinal IA

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class AssetConsumer(AsyncWebsocketConsumer):
    """
    Consumer WebSocket assíncrono para atualizações em tempo real de um ativo.

    Fluxo:
        connect()    — cliente abre conexão → ingresa no grupo `asset_{ticker}`
        disconnect() — cliente fecha conexão → sai do grupo
        receive()    — mensagem do cliente → broadcast para o grupo (opcional)
        ai_signal()  — mensagem do grupo enviada pela task Celery → encaminha ao cliente

    Grupos de Channel:
        Cada ticker tem seu próprio grupo: `asset_PETR4`, `asset_WINM25`, etc.
        A task `run_ai_analysis` publica no grupo após processar o sinal IA.

    Uso no frontend:
        const ws = new WebSocket('ws://host/ws/asset/PETR4/');
        ws.onmessage = (e) => { const data = JSON.parse(e.data); ... };
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticker      = ''
        self.group_name  = ''

    async def connect(self):
        """
        Aceita a conexão WebSocket e adiciona o cliente ao grupo do ticker.

        O ticker é extraído da URL: ws/asset/<ticker>/
        Rejeita a conexão (close 4003) se o ticker estiver ausente.
        """
        self.ticker     = self.scope['url_route']['kwargs'].get('ticker', '').upper()
        self.group_name = f'asset_{self.ticker}'

        if not self.ticker:
            logger.warning('[AssetConsumer] Conexão rejeitada — ticker ausente.')
            await self.close(code=4003)
            return

        # Adiciona este canal ao grupo do ticker para receber broadcasts
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

        logger.debug(
            '[AssetConsumer] Cliente conectado ao grupo %s (channel=%s)',
            self.group_name, self.channel_name,
        )

    async def disconnect(self, close_code):
        """
        Remove o cliente do grupo ao desconectar.

        Args:
            close_code: código de fechamento WebSocket.
        """
        if self.group_name:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )
            logger.debug(
                '[AssetConsumer] Cliente desconectado do grupo %s (code=%s)',
                self.group_name, close_code,
            )

    async def receive(self, text_data=None, bytes_data=None):
        """
        Recebe mensagens do cliente via WebSocket.

        Por enquanto apenas ecoa a mensagem de volta (ping/pong) para
        manter a conexão viva. Pode ser estendido para comandos do cliente.

        Args:
            text_data:  payload de texto recebido (JSON esperado).
            bytes_data: payload binário (não utilizado).
        """
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            logger.debug('[AssetConsumer] Payload não-JSON recebido: %s', text_data[:100])
            return

        # Pong simples para heartbeat do cliente
        if data.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    # ── Handlers de mensagens do Channel Layer ────────────────────────────────

    async def ai_signal(self, event):
        """
        Handler para mensagens do tipo `ai_signal` enviadas pela task Celery.

        A task `run_ai_analysis` publica via group_send():
            {
                'type':       'ai_signal',
                'ticker':     'PETR4',
                'signal':     'BULLISH',
                'confidence': 78.5,
                'synthesis':  '...',
            }

        Este handler encaminha o payload JSON para o cliente WebSocket conectado.

        Args:
            event: dict com os dados do sinal IA.
        """
        payload = {
            'type':       'ai_signal',
            'ticker':     event.get('ticker', self.ticker),
            'signal':     event.get('signal', 'NEUTRAL'),
            'confidence': event.get('confidence', 0),
            'synthesis':  event.get('synthesis', ''),
        }

        logger.debug(
            '[AssetConsumer] Enviando sinal IA para cliente — %s | %s | %.1f%%',
            payload['ticker'], payload['signal'], payload['confidence'] or 0,
        )

        await self.send(text_data=json.dumps(payload, ensure_ascii=False))
