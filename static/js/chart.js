/**
 * chart.js — Integração TradingView Lightweight Charts
 *
 * Tarefas implementadas:
 *   3.3.2 — Inicialização do createChart() com dark mode (fundo #0A0E1A)
 *   3.3.3 — loadChartData(ticker, timeframe) com fetch AJAX para /market-data/ohlc-data/
 *   3.3.4 — Integração com busca de ticker e seletor de timeframe
 */

'use strict';

// ── Estado global do gráfico ─────────────────────────────────────────────────
let _chart = null;
let _candleSeries = null;
let _activeTicker = null;
let _activeTimeframe = '15m';
const CHART_CONTAINER_ID = 'chart-container';
const CHART_PLACEHOLDER_ID = 'chart-placeholder';

// ── Formatação de números ────────────────────────────────────────────────────
function formatPrice(value) {
    if (value == null || isNaN(value)) return '—';
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(value);
}

function formatVolume(value) {
    if (value == null || isNaN(value)) return '—';
    if (value >= 1_000_000) return (value / 1_000_000).toFixed(1) + 'M';
    if (value >= 1_000) return (value / 1_000).toFixed(1) + 'K';
    return value.toString();
}

// ── Inicialização do gráfico (3.3.2) ─────────────────────────────────────────
function initChart() {
    const container = document.getElementById(CHART_CONTAINER_ID);
    if (!container || !window.LightweightCharts) {
        console.warn('[chart.js] LightweightCharts não disponível ou container não encontrado.');
        return;
    }

    // Destruir instância anterior se existir
    if (_chart) {
        _chart.remove();
        _chart = null;
        _candleSeries = null;
    }

    const containerWidth = container.clientWidth || 800;

    _chart = LightweightCharts.createChart(container, {
        width: containerWidth,
        height: 420,
        layout: {
            background: { type: 'solid', color: '#0F1629' },
            textColor: '#9CA3AF',
            fontSize: 12,
            fontFamily: "'Inter', system-ui, sans-serif",
        },
        grid: {
            vertLines: { color: '#1F2937', style: LightweightCharts.LineStyle.Dashed },
            horzLines: { color: '#1F2937', style: LightweightCharts.LineStyle.Dashed },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                color: '#3B82F6',
                labelBackgroundColor: '#1D4ED8',
            },
            horzLine: {
                color: '#3B82F6',
                labelBackgroundColor: '#1D4ED8',
            },
        },
        rightPriceScale: {
            borderColor: '#1F2937',
            textColor: '#9CA3AF',
        },
        timeScale: {
            borderColor: '#1F2937',
            timeVisible: true,
            secondsVisible: false,
            tickMarkFormatter: (time, tickMarkType, locale) => {
                const date = new Date(time * 1000);
                const options = { timeZone: 'America/Sao_Paulo' };
                if (tickMarkType === LightweightCharts.TickMarkType.Year) {
                    return date.toLocaleDateString('pt-BR', { year: 'numeric', ...options });
                }
                if (tickMarkType === LightweightCharts.TickMarkType.Month) {
                    return date.toLocaleDateString('pt-BR', { month: 'short', ...options });
                }
                if (tickMarkType === LightweightCharts.TickMarkType.DayOfMonth) {
                    return date.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', ...options });
                }
                return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', ...options });
            },
        },
        localization: {
            locale: 'pt-BR',
            priceFormatter: formatPrice,
        },
        handleScroll: { mouseWheel: true, pressedMouseMove: true },
        handleScale: { mouseWheel: true, pinch: true },
    });

    // Série de candlestick
    _candleSeries = _chart.addCandlestickSeries({
        upColor: '#10B981',
        downColor: '#EF4444',
        borderUpColor: '#10B981',
        borderDownColor: '#EF4444',
        wickUpColor: '#10B981',
        wickDownColor: '#EF4444',
    });

    // Crosshair: atualizar barra de preços ao mover o mouse
    _chart.subscribeCrosshairMove(updatePriceBar);

    // Responsividade: redimensionar ao mudar o tamanho da janela
    window.addEventListener('resize', () => {
        if (_chart && container) {
            _chart.resize(container.clientWidth, 420);
        }
    });
}

// ── Atualiza a barra de preços no topo do gráfico ───────────────────────────
function updatePriceBar(param) {
    if (!param || !param.seriesData) return;
    const data = param.seriesData.get(_candleSeries);
    if (!data) return;

    const elPrice = document.getElementById('chart-current-price');
    const elChange = document.getElementById('chart-price-change');
    const elOpen = document.getElementById('chart-open');
    const elHigh = document.getElementById('chart-high');
    const elLow = document.getElementById('chart-low');
    const elVol = document.getElementById('chart-vol');

    if (elPrice) elPrice.textContent = formatPrice(data.close);
    if (elOpen) elOpen.textContent = formatPrice(data.open);
    if (elHigh) elHigh.textContent = formatPrice(data.high);
    if (elLow) elLow.textContent = formatPrice(data.low);
    if (elVol && data.volume != null) elVol.textContent = formatVolume(data.volume);

    if (elChange && data.open && data.close) {
        const diff = data.close - data.open;
        const pct = ((diff / data.open) * 100).toFixed(2);
        const sign = diff >= 0 ? '+' : '';
        elChange.textContent = `${sign}${formatPrice(diff)} (${sign}${pct}%)`;
        elChange.className = diff >= 0
            ? 'text-sm font-medium tabular-nums text-emerald-400'
            : 'text-sm font-medium tabular-nums text-red-400';
    }
}

// ── Carrega dados OHLC do servidor (3.3.3) ───────────────────────────────────
async function loadChartData(ticker, timeframe) {
    if (!ticker) return;

    ticker = ticker.toUpperCase().trim();
    timeframe = timeframe || _activeTimeframe || '15m';
    _activeTicker = ticker;
    _activeTimeframe = timeframe;

    // Mostrar estado de carregamento
    _showLoadingState(ticker);

    // Inicializar gráfico se ainda não foi criado
    if (!_chart) {
        initChart();
    }

    try {
        const url = `/market-data/ohlc-data/?ticker=${encodeURIComponent(ticker)}&timeframe=${encodeURIComponent(timeframe)}`;
        const response = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.error || `HTTP ${response.status}`);
        }

        const data = await response.json();

        if (!data.candles || data.candles.length === 0) {
            _showEmptyState(ticker);
            return;
        }

        // Alimentar série de candlestick
        _candleSeries.setData(data.candles);

        // Ajustar escala de tempo para mostrar os últimos dados
        _chart.timeScale().fitContent();

        // Atualizar elementos da UI
        _updateTickerDisplay(data);

        // Esconder placeholder
        _hidePlaceholder();

    } catch (err) {
        console.error('[chart.js] Erro ao carregar dados:', err);
        _showErrorState(ticker, err.message);
    }
}

// ── Atualiza exibição do ticker na UI ────────────────────────────────────────
function _updateTickerDisplay(data) {
    const ticker = data.ticker || _activeTicker;
    const assetName = data.asset_name || ticker;
    const assetType = data.asset_type || '';
    const lastCandle = data.candles[data.candles.length - 1];

    // Título do gráfico
    const elName = document.getElementById('chart-ticker-name');
    if (elName) elName.textContent = assetName;

    const elType = document.getElementById('chart-asset-type');
    if (elType) elType.textContent = assetType === 'STOCK' ? 'Ação' : assetType === 'FUTURE' ? 'Futuro' : assetType;

    // Badge no header
    const badge = document.getElementById('active-ticker-badge');
    const badgeLabel = document.getElementById('active-ticker-label');
    if (badge && badgeLabel) {
        badgeLabel.textContent = ticker;
        badge.style.display = 'flex';
    }

    // Barra de preço do último candle
    if (lastCandle) {
        const elPrice = document.getElementById('chart-current-price');
        const elChange = document.getElementById('chart-price-change');
        const elOpen = document.getElementById('chart-open');
        const elHigh = document.getElementById('chart-high');
        const elLow = document.getElementById('chart-low');
        const elVol = document.getElementById('chart-vol');

        if (elPrice) elPrice.textContent = formatPrice(lastCandle.close);
        if (elOpen) elOpen.textContent = formatPrice(lastCandle.open);
        if (elHigh) elHigh.textContent = formatPrice(lastCandle.high);
        if (elLow) elLow.textContent = formatPrice(lastCandle.low);
        if (elVol && lastCandle.volume != null) elVol.textContent = formatVolume(lastCandle.volume);

        if (elChange && lastCandle.open && lastCandle.close) {
            const diff = lastCandle.close - lastCandle.open;
            const pct = ((diff / lastCandle.open) * 100).toFixed(2);
            const sign = diff >= 0 ? '+' : '';
            elChange.textContent = `${sign}${formatPrice(diff)} (${sign}${pct}%)`;
            elChange.className = diff >= 0
                ? 'text-sm font-medium tabular-nums text-emerald-400'
                : 'text-sm font-medium tabular-nums text-red-400';
        }
    }

    // Emitir evento personalizado para que outros componentes (painel lateral) reajam
    document.body.dispatchEvent(new CustomEvent('ticker-changed', {
        detail: { ticker, assetType: data.asset_type },
        bubbles: true,
    }));
}

// ── Estados visuais do gráfico ────────────────────────────────────────────────
function _showLoadingState(ticker) {
    const placeholder = document.getElementById(CHART_PLACEHOLDER_ID);
    if (placeholder) {
        placeholder.style.display = 'flex';
        placeholder.innerHTML = `
            <div class="flex flex-col items-center gap-3 text-gray-500">
                <svg class="h-8 w-8 spin-slow text-blue-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                    <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
                </svg>
                <p class="text-sm">Carregando <span class="font-semibold text-blue-400">${ticker}</span>…</p>
            </div>
        `;
    }
}

function _showEmptyState(ticker) {
    const placeholder = document.getElementById(CHART_PLACEHOLDER_ID);
    if (placeholder) {
        placeholder.style.display = 'flex';
        placeholder.innerHTML = `
            <div class="flex flex-col items-center gap-3 text-gray-600">
                <svg class="h-10 w-10 text-gray-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" aria-hidden="true">
                    <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <p class="text-sm">Nenhum dado disponível para <span class="font-semibold text-gray-400">${ticker}</span></p>
                <p class="text-xs text-gray-700">Execute a coleta de dados na Sprint 4</p>
            </div>
        `;
    }
}

function _showErrorState(ticker, message) {
    const placeholder = document.getElementById(CHART_PLACEHOLDER_ID);
    if (placeholder) {
        placeholder.style.display = 'flex';
        placeholder.innerHTML = `
            <div class="flex flex-col items-center gap-3 text-gray-600">
                <svg class="h-10 w-10 text-red-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
                    <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                </svg>
                <p class="text-sm">Erro ao carregar <span class="font-semibold text-gray-400">${ticker}</span></p>
                <p class="text-xs text-red-600">${message}</p>
            </div>
        `;
    }
}

function _hidePlaceholder() {
    const placeholder = document.getElementById(CHART_PLACEHOLDER_ID);
    if (placeholder) {
        placeholder.style.display = 'none';
    }
}

// ── Seletor de timeframe (3.3.4) ─────────────────────────────────────────────
function selectTimeframe(tf) {
    _activeTimeframe = tf;

    // Atualizar estilo dos botões
    document.querySelectorAll('.tf-btn').forEach(btn => {
        const isActive = btn.dataset.timeframe === tf;
        btn.classList.toggle('bg-blue-600', isActive);
        btn.classList.toggle('text-white', isActive);
        btn.classList.toggle('text-gray-400', !isActive);
        btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    // Recarregar gráfico com novo timeframe
    if (_activeTicker) {
        loadChartData(_activeTicker, tf);
    }
}

// ── Integração com busca HTMX — seleção de ticker (3.3.4) ───────────────────
// Chamada a partir do partial de sugestões HTMX
function selectTickerFromSearch(ticker) {
    // Limpar campo de busca
    const searchInput = document.getElementById('dashboard-ticker-search');
    if (searchInput) {
        searchInput.value = ticker;
        // Fechar dropdown Alpine.js
        searchInput.dispatchEvent(new Event('input'));
    }

    // Carregar gráfico
    loadChartData(ticker, _activeTimeframe);
}

// ── Inicialização ao carregar o DOM ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Inicializar o gráfico vazio
    initChart();

    // Se houver ticker pré-selecionado (ex: via URL param), carregá-lo
    const urlParams = new URLSearchParams(window.location.search);
    const tickerParam = urlParams.get('ticker');
    if (tickerParam) {
        loadChartData(tickerParam, urlParams.get('tf') || '15m');
    }
});

// ── Exportar funções para uso global nos templates ───────────────────────────
window.loadChartData = loadChartData;
window.selectTimeframe = selectTimeframe;
window.selectTickerFromSearch = selectTickerFromSearch;
