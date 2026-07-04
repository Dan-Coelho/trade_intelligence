from django.db import models

from market_data.models import Asset


class NewsArticle(models.Model):
    """Artigo de notícia relacionado (ou não) a um ativo específico."""

    class Sentiment(models.TextChoices):
        BULLISH = "BULLISH", "Alta"
        BEARISH = "BEARISH", "Baixa"
        NEUTRAL = "NEUTRAL", "Neutro"

    asset = models.ForeignKey(
        Asset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="news_articles",
        verbose_name="Ativo",
    )
    title = models.CharField(max_length=500, verbose_name="Título")
    body = models.TextField(verbose_name="Corpo")
    source_url = models.URLField(max_length=2000, verbose_name="URL da Fonte")
    source_name = models.CharField(max_length=100, verbose_name="Nome da Fonte")
    sentiment = models.CharField(
        max_length=10,
        choices=Sentiment.choices,
        default=Sentiment.NEUTRAL,
        verbose_name="Sentimento",
    )
    sentiment_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Pontuação de Sentimento",
    )
    published_at = models.DateTimeField(verbose_name="Publicado em")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Artigo de Notícia"
        verbose_name_plural = "Artigos de Notícias"
        ordering = ["-published_at"]

    def __str__(self):
        ticker = self.asset.ticker if self.asset else "Geral"
        return f"[{ticker}] {self.title[:80]}"


class MacroIndicator(models.Model):
    """Indicador macroeconômico (SELIC, IPCA, PIB, USD/BRL, etc.)."""

    name = models.CharField(max_length=100, verbose_name="Nome")
    source = models.CharField(max_length=100, verbose_name="Fonte")
    reference_date = models.DateField(verbose_name="Data de Referência")
    value = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        verbose_name="Valor",
    )
    unit = models.CharField(max_length=20, verbose_name="Unidade")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Indicador Macro"
        verbose_name_plural = "Indicadores Macro"
        ordering = ["name", "-reference_date"]
        unique_together = [("name", "reference_date")]

    def __str__(self):
        return f"{self.name} | {self.reference_date} | {self.value} {self.unit}"
