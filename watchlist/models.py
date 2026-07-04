from django.conf import settings
from django.db import models

from market_data.models import Asset


class Watchlist(models.Model):
    """Ativo monitorado na watchlist de um usuário."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
        verbose_name="Usuário",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
        verbose_name="Ativo",
    )
    display_order = models.IntegerField(default=0, verbose_name="Ordem de Exibição")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Watchlist"
        verbose_name_plural = "Watchlists"
        unique_together = [("user", "asset")]
        ordering = ["user", "display_order", "asset__ticker"]

    def __str__(self):
        return f"{self.user.email} → {self.asset.ticker}"


class PriceAlert(models.Model):
    """Alerta de preço configurado pelo usuário para um ativo."""

    class Condition(models.TextChoices):
        ABOVE = "ABOVE", "Acima de"
        BELOW = "BELOW", "Abaixo de"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="price_alerts",
        verbose_name="Usuário",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="price_alerts",
        verbose_name="Ativo",
    )
    condition = models.CharField(
        max_length=10,
        choices=Condition.choices,
        verbose_name="Condição",
    )
    target_price = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name="Preço Alvo",
    )
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    is_triggered = models.BooleanField(default=False, verbose_name="Disparado")
    triggered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Disparado em",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Alerta de Preço"
        verbose_name_plural = "Alertas de Preço"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.user.email} | {self.asset.ticker} | "
            f"{self.get_condition_display()} R$ {self.target_price}"
        )
