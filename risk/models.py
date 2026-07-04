from django.conf import settings
from django.db import models

from market_data.models import Asset


class RiskCalculation(models.Model):
    """Cálculo de gestão de risco e dimensionamento de posição para um ativo."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="risk_calculations",
        verbose_name="Usuário",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="risk_calculations",
        verbose_name="Ativo",
    )
    atr_value = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name="Valor ATR",
    )
    suggested_stop_loss = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name="Stop Loss Sugerido",
    )
    user_capital = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name="Capital do Usuário (R$)",
    )
    position_size = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        verbose_name="Tamanho da Posição",
    )
    kelly_fraction = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        verbose_name="Fração de Kelly",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Cálculo de Risco"
        verbose_name_plural = "Cálculos de Risco"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.user.email} | {self.asset.ticker} | "
            f"ATR {self.atr_value} | Stop {self.suggested_stop_loss}"
        )
