from django.contrib import admin

from .models import Asset, OHLCCandle


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("ticker", "name", "asset_type", "exchange", "created_at")
    list_filter = ("asset_type", "exchange")
    search_fields = ("ticker", "name")
    ordering = ("ticker",)


@admin.register(OHLCCandle)
class OHLCCandleAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "timeframe",
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )
    list_filter = ("asset__asset_type", "timeframe", "asset")
    search_fields = ("asset__ticker",)
    ordering = ("asset", "timeframe", "timestamp")
    date_hierarchy = "timestamp"
