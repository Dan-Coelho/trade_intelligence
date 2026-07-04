from django.db import models

from market_data.models import Asset


class TechnicalIndicator(models.Model):
    """Armazena o resultado calculado de um indicador técnico para um ativo."""

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="technical_indicators",
        verbose_name="Ativo",
    )
    indicator_name = models.CharField(
        max_length=50,
        verbose_name="Nome do Indicador",
    )
    timeframe = models.CharField(max_length=10, verbose_name="Timeframe")
    timestamp = models.DateTimeField(verbose_name="Timestamp")
    values = models.JSONField(verbose_name="Valores")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Indicador Técnico"
        verbose_name_plural = "Indicadores Técnicos"
        ordering = ["asset", "indicator_name", "timeframe", "-timestamp"]

    def __str__(self):
        return (
            f"{self.asset.ticker} | {self.indicator_name} | "
            f"{self.timeframe} | {self.timestamp:%Y-%m-%d %H:%M}"
        )


class CandlestickPattern(models.Model):
    """Padrão de candle identificado em um ativo para um determinado timeframe."""

    class Direction(models.TextChoices):
        BULLISH = "BULLISH", "Alta"
        BEARISH = "BEARISH", "Baixa"
        NEUTRAL = "NEUTRAL", "Neutro"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="candlestick_patterns",
        verbose_name="Ativo",
    )
    pattern_name = models.CharField(
        max_length=100,
        verbose_name="Nome do Padrão",
    )
    timeframe = models.CharField(max_length=10, verbose_name="Timeframe")
    timestamp = models.DateTimeField(verbose_name="Timestamp")
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        verbose_name="Direção",
    )
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Confiança (%)",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Padrão de Candlestick"
        verbose_name_plural = "Padrões de Candlestick"
        ordering = ["asset", "timeframe", "-timestamp"]

    def __str__(self):
        return (
            f"{self.asset.ticker} | {self.pattern_name} | "
            f"{self.direction} | {self.timestamp:%Y-%m-%d %H:%M}"
        )
