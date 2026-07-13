# watchlist/tasks.py — Task Celery de verificação de alertas de preço
#
# Tarefa 7.4.5 — check_price_alerts: agendada a cada 1 minuto,
#   verifica PriceAlert.objects.filter(is_active=True),
#   compara com último preço, publica notificação via Channels se condição satisfeita.

import logging
from datetime import datetime, timezone

from asgiref.sync import async_to_sync
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name='watchlist.tasks.check_price_alerts',
    ignore_result=True,
)
def check_price_alerts() -> None:
    """
    Verifica todos os alertas de preço ativos e dispara notificações via
    Django Channels quando a condição for satisfeita.

    Fluxo por alerta:
        1. Busca o último preço disponível para o ativo (último OHLCCandle diário).
        2. Compara com target_price conforme a condition (ABOVE / BELOW).
        3. Se condição satisfeita:
           a. Marca o alerta como is_triggered=True e registra triggered_at.
           b. Publica mensagem no channel group `alert_{user_id}` via Channels.
        4. Alertas já disparados (is_triggered=True) são ignorados.

    Agendamento: definido no CELERY_BEAT_SCHEDULE (a cada 60 s).
    """
    from watchlist.models import PriceAlert  # noqa: PLC0415
    from market_data.models import OHLCCandle  # noqa: PLC0415

    alerts = (
        PriceAlert.objects
        .filter(is_active=True, is_triggered=False)
        .select_related('asset', 'user')
    )

    if not alerts.exists():
        logger.debug('[check_price_alerts] Nenhum alerta ativo encontrado.')
        return

    triggered_count = 0

    for alert in alerts:
        # ── Buscar último preço disponível ────────────────────────────────────
        last_candle = (
            OHLCCandle.objects
            .filter(asset=alert.asset)
            .order_by('-timestamp')
            .values('close')
            .first()
        )

        if last_candle is None:
            logger.debug(
                '[check_price_alerts] Sem candles para %s — alerta id=%d ignorado.',
                alert.asset.ticker, alert.pk,
            )
            continue

        current_price = float(last_candle['close'])
        target_price  = float(alert.target_price)
        condition     = alert.condition

        # ── Verificar condição ────────────────────────────────────────────────
        triggered = (
            (condition == 'ABOVE' and current_price >= target_price) or
            (condition == 'BELOW' and current_price <= target_price)
        )

        if not triggered:
            continue

        # ── Marcar como disparado ─────────────────────────────────────────────
        alert.is_triggered = True
        alert.triggered_at  = datetime.now(tz=timezone.utc)
        alert.save(update_fields=['is_triggered', 'triggered_at', 'updated_at'])

        triggered_count += 1

        logger.info(
            '[check_price_alerts] Alerta DISPARADO — id=%d | user=%s | %s %s R$ %.4f (atual: R$ %.4f)',
            alert.pk, alert.user.email, alert.asset.ticker,
            condition, target_price, current_price,
        )

        # ── Publicar via Django Channels ──────────────────────────────────────
        _publish_alert_notification(alert, current_price)

    if triggered_count:
        logger.info('[check_price_alerts] %d alerta(s) disparado(s) nesta execução.', triggered_count)


def _publish_alert_notification(alert, current_price: float) -> None:
    """
    Publica notificação de alerta disparado no channel group `alert_{user_id}`.

    O frontend pode conectar-se via WebSocket ao endpoint ws/alerts/<user_id>/
    (implementado na Sprint 7) para receber notificações em tempo real.

    Args:
        alert:         instância de PriceAlert com is_triggered=True.
        current_price: preço atual do ativo que satisfez a condição.
    """
    try:
        from channels.layers import get_channel_layer  # noqa: PLC0415

        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.warning('[check_price_alerts] Channel layer não configurado — notificação não publicada.')
            return

        group_name = f'alert_{alert.user_id}'
        message = {
            'type':          'price_alert',   # handler no consumer (se implementado)
            'alert_id':      alert.pk,
            'ticker':        alert.asset.ticker,
            'condition':     alert.condition,
            'target_price':  float(alert.target_price),
            'current_price': round(current_price, 4),
            'triggered_at':  alert.triggered_at.isoformat() if alert.triggered_at else None,
            'message': (
                f"⚡ {alert.asset.ticker} {alert.get_condition_display()} "
                f"R$ {alert.target_price} — preço atual: R$ {current_price:.4f}"
            ),
        }

        async_to_sync(channel_layer.group_send)(group_name, message)

        logger.debug(
            '[check_price_alerts] Notificação publicada no grupo %s — %s',
            group_name, message['message'],
        )
    except Exception as exc:  # noqa: BLE001
        logger.error('[check_price_alerts] Erro ao publicar notificação: %s', exc)
