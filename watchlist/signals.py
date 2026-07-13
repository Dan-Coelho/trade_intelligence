# watchlist/signals.py — Django signals do app watchlist
#
# Tarefa 7.4.6 — Signal post_save em PriceAlert para log de auditoria

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _register_signals():
    """
    Registra todos os signals do app watchlist.

    Chamada pelo WatchlistConfig.ready() em apps.py. A importação do model
    ocorre dentro da função para garantir que o Django ORM está completamente
    inicializado, evitando erros de AppRegistryNotReady.
    """
    from watchlist.models import PriceAlert  # noqa: PLC0415

    @receiver(
        post_save,
        sender=PriceAlert,
        dispatch_uid='pricealert_post_save_audit_log',
    )
    def pricealert_post_save(sender, instance, created, **kwargs):
        """
        Signal post_save disparado após cada persistência de PriceAlert.

        Comportamento (log de auditoria):
            - Ao criar: registra criação do alerta com ticker, condição e preço alvo.
            - Ao atualizar: registra mudança de estado (especialmente is_triggered).
            - Nunca interrompe a operação principal de gravação.

        Args:
            sender:   classe do model (PriceAlert)
            instance: instância recém-salva do PriceAlert
            created:  True se o registro foi criado; False se foi atualizado
            **kwargs: argumentos adicionais do signal (ignorados)
        """
        ticker     = instance.asset.ticker if hasattr(instance, 'asset') else '?'
        user_email = instance.user.email   if hasattr(instance, 'user')  else '?'

        if created:
            logger.info(
                '[PriceAlert] Criado — user=%s | %s %s R$ %s (id=%d)',
                user_email,
                ticker,
                instance.get_condition_display(),
                instance.target_price,
                instance.pk,
            )
        else:
            # Detecta se o alerta foi disparado nesta atualização
            if instance.is_triggered:
                logger.info(
                    '[PriceAlert] DISPARADO — user=%s | %s %s R$ %s (id=%d)',
                    user_email,
                    ticker,
                    instance.get_condition_display(),
                    instance.target_price,
                    instance.pk,
                )
            else:
                logger.debug(
                    '[PriceAlert] Atualizado — user=%s | %s | is_active=%s (id=%d)',
                    user_email,
                    ticker,
                    instance.is_active,
                    instance.pk,
                )
