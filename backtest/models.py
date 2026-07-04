from django.conf import settings
from django.db import models

from market_data.models import Asset


class BacktestResult(models.Model):
    """Resultado de um backtest de estratégia executado pelo usuário."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="backtest_results",
        verbose_name="Usuário",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="backtest_results",
        verbose_name="Ativo",
    )
    strategy_name = models.CharField(max_length=100, verbose_name="Nome da Estratégia")
    start_date = models.DateField(verbose_name="Data de Início")
    end_date = models.DateField(verbose_name="Data de Fim")
    initial_capital = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name="Capital Inicial (R$)",
    )
    final_capital = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name="Capital Final (R$)",
    )
    win_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Taxa de Acerto (%)",
    )
    sharpe_ratio = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        verbose_name="Índice de Sharpe",
    )
    max_drawdown = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Drawdown Máximo (%)",
    )
    trades_log = models.JSONField(default=list, verbose_name="Log de Trades")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Resultado de Backtest"
        verbose_name_plural = "Resultados de Backtest"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.user.email} | {self.asset.ticker} | "
            f"{self.strategy_name} | {self.start_date} → {self.end_date}"
        )
