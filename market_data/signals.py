# market_data/signals.py — Django signals do app market_data
#
# Implementações:
#   4.6.1 — Signal post_save em OHLCCandle: ao criar um novo candle, dispara
#            analysis.tasks.run_technical_analysis.delay(instance.asset_id)

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _register_signals():
    """
    Registra todos os signals do app market_data.

    Chamada pelo MarketDataConfig.ready() em apps.py. Importar as models aqui
    (dentro da função) garante que o Django ORM está completamente inicializado,
    evitando erros de AppRegistryNotReady.
    """
    # A importação local é intencional: evita circular imports durante o boot do Django.
    from .models import OHLCCandle  # noqa: PLC0415

    @receiver(post_save, sender=OHLCCandle, dispatch_uid='ohlccandle_post_save_run_analysis')
    def ohlccandle_post_save(sender, instance, created, **kwargs):
        """
        Signal post_save disparado após cada persistência de OHLCCandle.

        Comportamento:
            - Executado apenas quando `created=True` (candle novo, não atualização).
            - Dispara a task Celery `run_technical_analysis` passando o ID do ativo,
              permitindo que o cálculo de indicadores seja feito de forma assíncrona.
            - Se o módulo `analysis.tasks` ainda não estiver disponível (Sprint 5
              não concluída), o erro é suprimido e apenas um aviso é logado.

        Args:
            sender:   classe do model (OHLCCandle)
            instance: instância recém-salva do OHLCCandle
            created:  True se o registro foi criado; False se foi atualizado
            **kwargs: argumentos adicionais do signal (ignorados)
        """
        if not created:
            return

        asset_id = instance.asset_id
        ticker   = instance.asset.ticker if hasattr(instance, 'asset') else str(asset_id)

        logger.debug(
            '[signal:ohlccandle_post_save] Novo candle criado para %s (asset_id=%d). '
            'Disparando run_technical_analysis.',
            ticker,
            asset_id,
        )

        try:
            from analysis.tasks import run_technical_analysis  # noqa: PLC0415
            run_technical_analysis.delay(asset_id)
        except ImportError:
            # analysis.tasks ainda não existe (Sprint 5) — comportamento esperado
            logger.debug(
                '[signal:ohlccandle_post_save] analysis.tasks não disponível ainda '
                '(Sprint 5). Signal registrado mas task não disparada.'
            )
        except Exception as exc:  # noqa: BLE001
            # Nunca deixa o signal derrubar a operação principal de gravação
            logger.error(
                '[signal:ohlccandle_post_save] Erro ao disparar run_technical_analysis '
                'para asset_id=%d: %s',
                asset_id,
                exc,
            )
