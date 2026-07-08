/**
 * chart.js — Integração TradingView Lightweight Charts
 *
 * Tarefas implementadas:
 *   3.3.2 — Inicialização do createChart() com dark mode (fundo #0A0E1A)
 *   3.3.3 — loadChartData(ticker, timeframe) com fetch AJAX para /market-data/ohlc-data/
 *   3.3.4 — Integração com busca de ticker e seletor de timeframe
 *   5.2.2 — Overlay de Fibonacci como séries de linhas horizontais no gráfico
 *   5.3.3 — Overlay de Bollinger Bands (série de bandas) no gráfico principal
 *   5.3.4 — Sub-gráficos de RSI e MACD abaixo do candlestick principal
 */

'use strict';

// ── Estado global do gráfico ─────────────────────────────────────────────────
let _chart = null;
let _candleSeries = null;
let _activeTicker = null;
let _activeTimeframe = '15m';
const CHART_CONTAINER_ID = 'chart-container';
const CHART_PLACEHOLDER_ID = 'chart-placeholder';

// ── Estado Fibonacci ──────────────────────────────────────────────────────────
let _fibSeries = [];          // Array de séries de linhas do overlay Fibonacci
let _fibVisible = false;      // Visibilidade atual do overlay
let _fibData = null;          // Último conjunto de dados OHLC carregado (para recalcular)

// Paleta de cores para cada nível Fibonacci (ordem: 0% → 100%)
const FIB_COLORS = {
    '0.0%':   { color: '#94A3B8', label: '0.0%'   },
    '23.6%':  { color: '#F59E0B', label: '23.6%'  },
    '38.2%':  { color: '#10B981', label: '38.2%'  },
    '50.0%':  { color: '#3B82F6', label: '50.0%'  },
    '61.8%':  { color: '#A78BFA', label: '61.8%'  },  // nível dourado
    '78.6%':  { color: '#F97316', label: '78.6%'  },
    '100.0%': { color: '#94A3B8', label: '100.0%' },
};

// ── Estado Bollinger Bands (5.3.3) ───────────────────────────────────────────────
let _bbUpperSeries  = null;
let _bbMiddleSeries = null;
let _bbLowerSeries  = null;
let _bbAreaSeries   = null;   // Série de área para preencher entre upper e lower
let _bbVisible      = false;

// ── Estado sub-gráficos RSI e MACD (5.3.4) ────────────────────────────────────
let _rsiChart       = null;   // Instância de gráfico TradingView do RSI
let _rsiSeries      = null;
let _macdChart      = null;   // Instância de gráfico TradingView do MACD
let _macdLineSeries = null;
let _macdSigSeries  = null;
let _macdHistSeries = null;
let _subchartsReady = false;

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

        // Guardar dados para recálculo do Fibonacci
        _fibData = data.candles;

        // Ajustar escala de tempo para mostrar os últimos dados
        _chart.timeScale().fitContent();

        // Atualizar elementos da UI
        _updateTickerDisplay(data);

        // Esconder placeholder
        _hidePlaceholder();

        // Re-desenhar Fibonacci se estiver visível
        if (_fibVisible) {
            drawFibonacciLevels();
        }

        // Atualizar sub-gráficos de RSI/MACD e overlay Bollinger (5.3.3/5.3.4)
        updateIndicatorCharts(ticker, timeframe);

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

// ── Overlay de Fibonacci (5.2.2) ─────────────────────────────────────────────

/**
 * Calcula os níveis de retração de Fibonacci a partir do high/low dos dados.
 *
 * @param {number} high  - Preço máximo do range
 * @param {number} low   - Preço mínimo do range
 * @returns {Object}     - Dict { '0.0%': price, '23.6%': price, ... }
 */
function calcFibLevels(high, low) {
    const range = high - low;
    return {
        '0.0%':   high,
        '23.6%':  high - range * 0.236,
        '38.2%':  high - range * 0.382,
        '50.0%':  high - range * 0.500,
        '61.8%':  high - range * 0.618,
        '78.6%':  high - range * 0.786,
        '100.0%': low,
    };
}

/**
 * Remove todos os overlays de Fibonacci ativos do gráfico.
 */
function clearFibonacciLevels() {
    _fibSeries.forEach(series => {
        try { _chart.removeSeries(series); } catch (_) {}
    });
    _fibSeries = [];

    // Esconder painel de legenda
    const legend = document.getElementById('fib-legend');
    if (legend) legend.style.display = 'none';
}

/**
 * Desenha os níveis de Fibonacci como linhas horizontais no gráfico.
 *
 * Calcula o high e o low dos dados OHLC atualmente carregados e plota
 * 7 linhas horizontais coloridas com label de preço e nível percentual.
 * As linhas são representadas como séries de linha com dois pontos
 * (primeiro e último timestamp dos dados).
 *
 * @param {number|null} customHigh - High customizado (opcional, usa range total se omitido)
 * @param {number|null} customLow  - Low customizado (opcional)
 */
function drawFibonacciLevels(customHigh = null, customLow = null) {
    if (!_chart || !_candleSeries) {
        console.warn('[Fibonacci] Gráfico não inicializado.');
        return;
    }
    if (!_fibData || _fibData.length === 0) {
        console.warn('[Fibonacci] Sem dados OHLC para calcular Fibonacci.');
        return;
    }

    // Limpa overlays anteriores
    clearFibonacciLevels();

    // Determina high/low do range (últimos 50 candles para relevância)
    const recentData = _fibData.slice(-50);
    const high = customHigh ?? Math.max(...recentData.map(c => c.high ?? c.close));
    const low  = customLow  ?? Math.min(...recentData.map(c => c.low  ?? c.close));

    if (high <= low) {
        console.warn('[Fibonacci] Range inválido: high <= low.');
        return;
    }

    const levels = calcFibLevels(high, low);
    const firstTime = _fibData[0].time;
    const lastTime  = _fibData[_fibData.length - 1].time;

    // Cria uma série de linha por nível
    Object.entries(levels).forEach(([label, price]) => {
        const meta = FIB_COLORS[label] || { color: '#6B7280' };

        const lineSeries = _chart.addLineSeries({
            color:           meta.color,
            lineWidth:       1,
            lineStyle:       LightweightCharts.LineStyle.Dashed,
            priceLineVisible: false,
            lastValueVisible: true,
            title:           `Fib ${label}`,
            crosshairMarkerVisible: false,
        });

        // Dois pontos definem uma linha horizontal no período visível
        lineSeries.setData([
            { time: firstTime, value: price },
            { time: lastTime,  value: price },
        ]);

        _fibSeries.push(lineSeries);
    });

    _fibVisible = true;

    // Atualizar estado do botão de toggle
    _updateFibButton(true);

    // Exibir legenda de Fibonacci
    _renderFibLegend(levels);

    console.info(
        `[Fibonacci] ${Object.keys(levels).length} níveis desenhados. Range: ${formatPrice(low)} – ${formatPrice(high)}`
    );
}

/**
 * Alterna a visibilidade do overlay de Fibonacci.
 * Se estiver visível, remove. Se não estiver, desenha.
 */
function toggleFibonacci() {
    if (_fibVisible) {
        clearFibonacciLevels();
        _fibVisible = false;
        _updateFibButton(false);
    } else {
        drawFibonacciLevels();
    }
}

/** Atualiza o estilo do botão de Fibonacci no DOM. */
function _updateFibButton(active) {
    const btn = document.getElementById('btn-fibonacci');
    if (!btn) return;
    btn.classList.toggle('bg-amber-600',   active);
    btn.classList.toggle('text-white',     active);
    btn.classList.toggle('text-amber-400', !active);
    btn.classList.toggle('bg-transparent', !active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    btn.title = active ? 'Ocultar Fibonacci' : 'Exibir Fibonacci';
}

/** Renderiza a legenda de níveis Fibonacci no painel lateral. */
function _renderFibLegend(levels) {
    const legend = document.getElementById('fib-legend');
    if (!legend) return;

    legend.innerHTML = `
        <p class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Retração Fibonacci</p>
        <ul class="space-y-1">
            ${Object.entries(levels).map(([label, price]) => {
                const meta = FIB_COLORS[label] || { color: '#6B7280' };
                return `
                    <li class="flex justify-between items-center text-xs">
                        <span class="flex items-center gap-1.5">
                            <span class="inline-block w-3 h-0.5 rounded" style="background:${meta.color}"></span>
                            <span class="text-gray-400">${label}</span>
                        </span>
                        <span class="font-mono tabular-nums" style="color:${meta.color}">
                            ${formatPrice(price)}
                        </span>
                    </li>
                `;
            }).join('')}
        </ul>
    `;
    legend.style.display = 'block';
}

// ── Overlay Bollinger Bands (5.3.3) ─────────────────────────────────────────────

/**
 * Remove todas as séries de Bollinger Bands do gráfico principal.
 */
function clearBollingerBands() {
    [_bbUpperSeries, _bbMiddleSeries, _bbLowerSeries, _bbAreaSeries].forEach(s => {
        if (s) { try { _chart.removeSeries(s); } catch (_) {} }
    });
    _bbUpperSeries = _bbMiddleSeries = _bbLowerSeries = _bbAreaSeries = null;
    _bbVisible = false;
    _updateBBButton(false);
}

/**
 * Renderiza o overlay de Bollinger Bands no gráfico de candlestick.
 *
 * Plota 3 séries de linha (upper, middle, lower) e uma série de área semitransparente
 * entre upper e lower para visualizar a "banda".
 *
 * @param {Array} bbandsData - Array de {time, upper, middle, lower} do endpoint /analysis/indicators/
 */
function drawBollingerBands(bbandsData) {
    if (!_chart) return;
    if (!bbandsData || bbandsData.length === 0) {
        console.warn('[BBands] Sem dados de Bollinger Bands para renderizar.');
        return;
    }

    clearBollingerBands();

    const validData = bbandsData.filter(
        d => d.upper != null && d.middle != null && d.lower != null
    );
    if (validData.length === 0) return;

    // Banda superior
    _bbUpperSeries = _chart.addLineSeries({
        color:            'rgba(59,130,246,0.7)',
        lineWidth:        1,
        lineStyle:        LightweightCharts.LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
        title:            'BB Upper',
        crosshairMarkerVisible: false,
    });
    _bbUpperSeries.setData(validData.map(d => ({ time: d.time, value: d.upper })));

    // Banda média (SMA)
    _bbMiddleSeries = _chart.addLineSeries({
        color:            'rgba(59,130,246,0.5)',
        lineWidth:        1,
        lineStyle:        LightweightCharts.LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
        title:            'BB Middle',
        crosshairMarkerVisible: false,
    });
    _bbMiddleSeries.setData(validData.map(d => ({ time: d.time, value: d.middle })));

    // Banda inferior
    _bbLowerSeries = _chart.addLineSeries({
        color:            'rgba(59,130,246,0.7)',
        lineWidth:        1,
        lineStyle:        LightweightCharts.LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
        title:            'BB Lower',
        crosshairMarkerVisible: false,
    });
    _bbLowerSeries.setData(validData.map(d => ({ time: d.time, value: d.lower })));

    _bbVisible = true;
    _updateBBButton(true);
    console.info(`[BBands] ${validData.length} pontos de Bollinger Bands renderizados.`);
}

/** Alterna a visibilidade do overlay de Bollinger Bands. */
function toggleBollingerBands() {
    if (_bbVisible) {
        clearBollingerBands();
    } else {
        // Busca dados e redesenha se já tiver um ticker ativo
        if (_activeTicker) {
            loadIndicators(_activeTicker, _activeTimeframe).then(data => {
                if (data?.bbands) drawBollingerBands(data.bbands);
            });
        }
    }
}

function _updateBBButton(active) {
    const btn = document.getElementById('btn-bollinger');
    if (!btn) return;
    btn.classList.toggle('bg-blue-600',    active);
    btn.classList.toggle('text-white',     active);
    btn.classList.toggle('text-blue-400',  !active);
    btn.classList.toggle('bg-transparent', !active);
    btn.setAttribute('aria-pressed', active ? 'true' : 'false');
}

// ── Sub-gráficos RSI e MACD (5.3.4) ────────────────────────────────────────────

/** Opções de layout compartilhadas entre os sub-gráficos. */
const SUBCHART_OPTIONS = {
    layout: {
        background: { type: 'solid', color: '#0D1117' },
        textColor:  '#6B7280',
        fontSize:   10,
        fontFamily: "'Inter', system-ui, sans-serif",
    },
    grid: {
        vertLines: { color: '#161B22' },
        horzLines: { color: '#161B22' },
    },
    rightPriceScale: { borderColor: '#21262D', textColor: '#6B7280' },
    timeScale:       { borderColor: '#21262D', timeVisible: true, secondsVisible: false },
    handleScroll:    { mouseWheel: true, pressedMouseMove: true },
    handleScale:     { mouseWheel: true },
    crosshair:       { mode: LightweightCharts.CrosshairMode.Normal },
};

/**
 * Inicializa o sub-gráfico de RSI no container #rsi-chart-container.
 * Cria o gráfico com linha de sobrecompra (70) e sobrevenda (30).
 */
function _initRsiChart() {
    const container = document.getElementById('rsi-chart-container');
    if (!container || !window.LightweightCharts) return;
    if (_rsiChart) { _rsiChart.remove(); _rsiChart = null; }

    _rsiChart = LightweightCharts.createChart(container, {
        ...SUBCHART_OPTIONS,
        width:  container.clientWidth || 800,
        height: 120,
    });

    // Série principal do RSI
    _rsiSeries = _rsiChart.addLineSeries({
        color:            '#A78BFA',
        lineWidth:        2,
        priceLineVisible: false,
        lastValueVisible: true,
        title:            'RSI(14)',
    });

    // Linhas de referência: sobrecompra 70 e sobrevenda 30
    _rsiSeries.createPriceLine({ price: 70, color: '#EF4444', lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'OB' });
    _rsiSeries.createPriceLine({ price: 30, color: '#10B981', lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: true, title: 'OS' });
    _rsiSeries.createPriceLine({ price: 50, color: '#4B5563', lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted, axisLabelVisible: false });

    // Sincroniza range de tempo com o gráfico principal
    _chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range && _rsiChart) _rsiChart.timeScale().setVisibleLogicalRange(range);
    });

    // Responsividade
    window.addEventListener('resize', () => {
        if (_rsiChart && container) _rsiChart.resize(container.clientWidth, 120);
    });
}

/**
 * Inicializa o sub-gráfico de MACD no container #macd-chart-container.
 * Plota a linha MACD, linha de sinal e histograma colorido.
 */
function _initMacdChart() {
    const container = document.getElementById('macd-chart-container');
    if (!container || !window.LightweightCharts) return;
    if (_macdChart) { _macdChart.remove(); _macdChart = null; }

    _macdChart = LightweightCharts.createChart(container, {
        ...SUBCHART_OPTIONS,
        width:  container.clientWidth || 800,
        height: 120,
    });

    // Linha MACD
    _macdLineSeries = _macdChart.addLineSeries({
        color:            '#3B82F6',
        lineWidth:        2,
        priceLineVisible: false,
        lastValueVisible: true,
        title:            'MACD',
    });

    // Linha de sinal
    _macdSigSeries = _macdChart.addLineSeries({
        color:            '#F59E0B',
        lineWidth:        1,
        lineStyle:        LightweightCharts.LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: true,
        title:            'Signal',
    });

    // Histograma (barras coloridas: verde acima de zero, vermelho abaixo)
    _macdHistSeries = _macdChart.addHistogramSeries({
        color:            '#10B981',
        priceLineVisible: false,
        lastValueVisible: false,
    });

    // Sincroniza range de tempo com o gráfico principal
    _chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
        if (range && _macdChart) _macdChart.timeScale().setVisibleLogicalRange(range);
    });

    // Responsividade
    window.addEventListener('resize', () => {
        if (_macdChart && container) _macdChart.resize(container.clientWidth, 120);
    });
}

/**
 * Busca dados do endpoint /analysis/indicators/ e retorna o objeto JSON.
 *
 * @param {string} ticker    - Ticker do ativo
 * @param {string} timeframe - Timeframe
 * @returns {Promise<Object|null>} - Dados de indicadores ou null em caso de erro
 */
async function loadIndicators(ticker, timeframe) {
    try {
        const url = `/analysis/indicators/?ticker=${encodeURIComponent(ticker)}&timeframe=${encodeURIComponent(timeframe)}&limit=200`;
        const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!res.ok) return null;
        return await res.json();
    } catch (err) {
        console.error('[Indicators] Erro ao buscar indicadores:', err);
        return null;
    }
}

/**
 * Atualiza os sub-gráficos (RSI, MACD) e o overlay de Bollinger Bands
 * com os dados buscados do endpoint /analysis/indicators/.
 *
 * Chamada automaticamente após loadChartData().
 *
 * @param {string} ticker    - Ticker do ativo
 * @param {string} timeframe - Timeframe
 */
async function updateIndicatorCharts(ticker, timeframe) {
    const data = await loadIndicators(ticker, timeframe);
    if (!data) return;

    // ── Inicializa sub-gráficos na primeira carga ─────────────────────────────
    if (!_subchartsReady) {
        _initRsiChart();
        _initMacdChart();
        _subchartsReady = true;
    }

    // ── RSI ───────────────────────────────────────────────────────────────────
    if (_rsiSeries && data.rsi?.length) {
        _rsiSeries.setData(
            data.rsi
                .filter(d => d.value != null)
                .map(d => ({ time: d.time, value: d.value }))
        );
        _rsiChart?.timeScale().fitContent();
    }

    // ── MACD ──────────────────────────────────────────────────────────────────
    if (_macdLineSeries && data.macd?.length) {
        const validMacd = data.macd.filter(d => d.macd != null);

        _macdLineSeries.setData(validMacd.map(d => ({ time: d.time, value: d.macd })));
        _macdSigSeries?.setData(
            validMacd.filter(d => d.signal != null).map(d => ({ time: d.time, value: d.signal }))
        );
        // Histograma: cor condicional por valor
        _macdHistSeries?.setData(
            validMacd.filter(d => d.hist != null).map(d => ({
                time:  d.time,
                value: d.hist,
                color: d.hist >= 0 ? '#10B981' : '#EF4444',
            }))
        );
        _macdChart?.timeScale().fitContent();
    }

    // ── Bollinger Bands (apenas se estiver visível) ───────────────────────────
    if (_bbVisible && data.bbands?.length) {
        drawBollingerBands(data.bbands);
    }

    // ── Atualiza snapshot no painel lateral ───────────────────────────────────
    if (data.latest) {
        _updateIndicatorSnapshot(data.latest);
    }
}

/** Atualiza os elementos HTML do painel lateral com os últimos valores. */
function _updateIndicatorSnapshot(latest) {
    const fields = {
        'indicator-rsi':        latest.rsi      != null ? latest.rsi.toFixed(2)      : null,
        'indicator-macd':       latest.macd     != null ? latest.macd.toFixed(4)     : null,
        'indicator-macd-sig':   latest.macd_signal != null ? latest.macd_signal.toFixed(4) : null,
        'indicator-bb-upper':   latest.bb_upper != null ? formatPrice(latest.bb_upper) : null,
        'indicator-bb-lower':   latest.bb_lower != null ? formatPrice(latest.bb_lower) : null,
        'indicator-atr':        latest.atr      != null ? latest.atr.toFixed(4)      : null,
    };
    Object.entries(fields).forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el && value != null) el.textContent = value;
    });

    // RSI colorido: vermelho se sobrecomprado (>70), verde se sobrevendido (<30)
    const rsiEl = document.getElementById('indicator-rsi');
    if (rsiEl && latest.rsi != null) {
        rsiEl.className = latest.rsi > 70
            ? 'font-mono text-red-400'
            : latest.rsi < 30
            ? 'font-mono text-emerald-400'
            : 'font-mono text-gray-300';
    }
}

// ── Exportar funções para uso global nos templates ───────────────────────────
window.loadChartData          = loadChartData;
window.selectTimeframe        = selectTimeframe;
window.selectTickerFromSearch = selectTickerFromSearch;
window.drawFibonacciLevels   = drawFibonacciLevels;
window.clearFibonacciLevels  = clearFibonacciLevels;
window.toggleFibonacci       = toggleFibonacci;
window.drawBollingerBands    = drawBollingerBands;
window.clearBollingerBands   = clearBollingerBands;
window.toggleBollingerBands  = toggleBollingerBands;
window.updateIndicatorCharts = updateIndicatorCharts;
