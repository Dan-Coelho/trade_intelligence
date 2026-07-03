from django.db import models


class Asset(models.Model):
    """Representa um ativo financeiro (ação, futuro, etc.)."""

    class AssetType(models.TextChoices):
        FUTURE = "FUTURE", "Futuro"
        STOCK = "STOCK", "Ação"

    ticker = models.CharField(max_length=20, unique=True, verbose_name="Ticker")
    name = models.CharField(max_length=255, verbose_name="Nome")
    asset_type = models.CharField(
        max_length=10,
        choices=AssetType.choices,
        verbose_name="Tipo de Ativo",
    )
    exchange = models.CharField(
        max_length=20,
        default="B3",
        verbose_name="Bolsa",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Ativo"
        verbose_name_plural = "Ativos"
        ordering = ["ticker"]

    def __str__(self):
        return f"{self.ticker} — {self.name}"


class OHLCCandle(models.Model):
    """Candle OHLCV para um ativo em um determinado timeframe."""

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="candles",
        verbose_name="Ativo",
    )
    timeframe = models.CharField(max_length=10, verbose_name="Timeframe")
    timestamp = models.DateTimeField(db_index=True, verbose_name="Timestamp")
    open = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Abertura"
    )
    high = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Máxima"
    )
    low = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Mínima"
    )
    close = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Fechamento"
    )
    volume = models.BigIntegerField(verbose_name="Volume")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Candle OHLC"
        verbose_name_plural = "Candles OHLC"
        unique_together = [("asset", "timestamp", "timeframe")]
        ordering = ["asset", "timeframe", "timestamp"]

    def __str__(self):
        return (
            f"{self.asset.ticker} | {self.timeframe} | {self.timestamp:%Y-%m-%d %H:%M}"
        )
