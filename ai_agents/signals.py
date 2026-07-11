# ai_agents/signals.py — Django signals do app ai_agents
#
# Implementações:
#   6.6.2 — Signal post_save em TechnicalIndicator: ao criar um novo indicador
#            técnico, dispara run_ai_analysis.delay(instance.asset_id).

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _register_signals():
    """
    Registra todos os signals do app ai_agents.

    Chamada pelo AiAgentsConfig.ready() em apps.py. A importação do model
    ocorre dentro da função para garantir que o Django ORM está completamente
    inicializado, evitando erros de AppRegistryNotReady.
    """
    # Importação local — intencional para evitar circular imports durante o boot
    from analysis.models import TechnicalIndicator  # noqa: PLC0415

    @receiver(
        post_save,
        sender=TechnicalIndicator,
        dispatch_uid='technicalindicator_post_save_run_ai_analysis',
    )
    def technicalindicator_post_save(sender, instance, created, **kwargs):
        """
        Signal post_save disparado após cada persistência de TechnicalIndicator.

        Comportamento:
            - Executado apenas quando `created=True` (novo indicador, não atualização).
            - Dispara a task Celery `run_ai_analysis` passando o asset_id do indicador,
              permitindo que o pipeline IA seja executado de forma assíncrona.
            - Erros são capturados e logados sem interromper a operação principal
              de gravação do indicador.

        Args:
            sender:   classe do model (TechnicalIndicator)
            instance: instância recém-salva do TechnicalIndicator
            created:  True se o registro foi criado; False se foi atualizado
            **kwargs: argumentos adicionais do signal (ignorados)
        """
        if not created:
            return

        asset_id = instance.asset_id
        ticker   = instance.asset.ticker if hasattr(instance, 'asset') else str(asset_id)

        logger.debug(
            '[signal:technicalindicator_post_save] Novo TechnicalIndicator criado para '
            '%s (asset_id=%d). Disparando run_ai_analysis.',
            ticker,
            asset_id,
        )

        try:
            from ai_agents.tasks import run_ai_analysis  # noqa: PLC0415
            run_ai_analysis.delay(asset_id)
        except ImportError:
            # Caso improvável: módulo ai_agents.tasks não disponível
            logger.warning(
                '[signal:technicalindicator_post_save] ai_agents.tasks não disponível. '
                'Signal registrado mas task não disparada.'
            )
        except Exception as exc:  # noqa: BLE001
            # Nunca deixa o signal derrubar a operação principal de gravação
            logger.error(
                '[signal:technicalindicator_post_save] Erro ao disparar run_ai_analysis '
                'para asset_id=%d: %s',
                asset_id,
                exc,
            )
