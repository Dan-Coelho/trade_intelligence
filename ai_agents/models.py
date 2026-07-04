from django.db import models

from market_data.models import Asset


class AISignal(models.Model):
    """Sinal de IA gerado pelo sistema multi-agente para um ativo."""

    class SignalType(models.TextChoices):
        BULLISH = "BULLISH", "Alta"
        BEARISH = "BEARISH", "Baixa"
        NEUTRAL = "NEUTRAL", "Neutro"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="ai_signals",
        verbose_name="Ativo",
    )
    signal_type = models.CharField(
        max_length=10,
        choices=SignalType.choices,
        verbose_name="Tipo de Sinal",
    )
    confidence_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Confiança (%)",
    )
    technical_justification = models.TextField(
        verbose_name="Justificativa Técnica",
    )
    fundamental_justification = models.TextField(
        blank=True,
        verbose_name="Justificativa Fundamentalista",
    )
    macro_justification = models.TextField(
        verbose_name="Justificativa Macroeconômica",
    )
    synthesis_text = models.TextField(
        verbose_name="Síntese",
    )
    timeframe = models.CharField(max_length=10, verbose_name="Timeframe")
    generated_at = models.DateTimeField(verbose_name="Gerado em")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Sinal de IA"
        verbose_name_plural = "Sinais de IA"
        ordering = ["-generated_at"]

    def __str__(self):
        return (
            f"{self.asset.ticker} | {self.signal_type} | "
            f"{self.confidence_pct}% | {self.generated_at:%Y-%m-%d %H:%M}"
        )
