from django.db import models

from market_data.models import Asset


class FundamentalData(models.Model):
    """Dados fundamentalistas de um ativo para uma data de referência."""

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="fundamental_data",
        verbose_name="Ativo",
    )
    reference_date = models.DateField(verbose_name="Data de Referência")
    pl_ratio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="P/L",
    )
    roe = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="ROE (%)",
    )
    dividend_yield = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Dividend Yield (%)",
    )
    ev_ebitda = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="EV/EBITDA",
    )
    raw_data = models.JSONField(default=dict, verbose_name="Dados Brutos")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Dado Fundamentalista"
        verbose_name_plural = "Dados Fundamentalistas"
        ordering = ["asset", "-reference_date"]
        unique_together = [("asset", "reference_date")]

    def __str__(self):
        return f"{self.asset.ticker} | {self.reference_date}"
