/**
 * static/js/websocket.js
 *
 * Tarefa 7.1.6 — Conexão WebSocket para atualizações em tempo real do sinal IA.
 *
 * Responsabilidades:
 *   - Conectar ao endpoint ws/asset/<ticker>/ ao carregar a página de um ativo.
 *   - Ao receber mensagem do servidor, atualizar o card de sinal IA via DOM.
 *   - Reconexão automática com back-off exponencial em caso de queda.
 *   - Heartbeat (ping) a cada 25 s para manter a conexão viva.
 *
 * Uso nos templates:
 *   <script src="{% static 'js/websocket.js' %}"></script>
 *   <script>
 *     TradeWS.connect('PETR4');          // conecta ao ticker
 *     // ou deixar auto-detect via data-ticker no elemento #ws-ticker
 *   </script>
 *
 * Elementos DOM esperados (ids únicos para testes de browser):
 *   #ai-signal-badge        — badge/pill com o valor do sinal (BULLISH/BEARISH/NEUTRAL)
 *   #ai-signal-confidence   — elemento com a confiança em %
 *   #ai-signal-synthesis    — elemento com o texto de síntese
 *   #ai-signal-card         — card container (recebe classe CSS do sinal)
 *   #ai-ws-status           — indicador de status da conexão (opcional)
 */

'use strict';

const TradeWS = (() => {
  // ── Configuração ──────────────────────────────────────────────────────────
  const WS_SCHEME       = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const MAX_RETRIES     = 8;
  const BASE_DELAY_MS   = 1_000;   // delay inicial de reconexão
  const MAX_DELAY_MS    = 30_000;  // cap do back-off exponencial
  const PING_INTERVAL   = 25_000;  // heartbeat a cada 25 s

  // ── Estado interno ────────────────────────────────────────────────────────
  let socket        = null;
  let ticker        = null;
  let retries       = 0;
  let pingTimer     = null;
  let reconnectTimer = null;

  // ── Helpers de DOM ────────────────────────────────────────────────────────

  /**
   * Atualiza o card de sinal IA no DOM com os dados recebidos via WebSocket.
   *
   * @param {Object} data - Payload da mensagem WebSocket.
   * @param {string} data.signal      - 'BULLISH' | 'BEARISH' | 'NEUTRAL'
   * @param {number} data.confidence  - 0–100
   * @param {string} data.synthesis   - Texto de síntese
   */
  function updateSignalCard(data) {
    const signal     = (data.signal     || 'NEUTRAL').toUpperCase();
    const confidence = typeof data.confidence === 'number' ? data.confidence : 0;
    const synthesis  = data.synthesis  || '';

    // Mapa de classes CSS por sinal
    const signalClasses = {
      BULLISH: 'signal--bullish',
      BEARISH: 'signal--bearish',
      NEUTRAL: 'signal--neutral',
    };

    // ── Badge do sinal ──────────────────────────────────────────────────────
    const badge = document.getElementById('ai-signal-badge');
    if (badge) {
      badge.textContent = signal;
      badge.className   = badge.className
        .replace(/signal--(bullish|bearish|neutral)/gi, '')
        .trim();
      badge.classList.add(signalClasses[signal] || 'signal--neutral');
    }

    // ── Confiança ───────────────────────────────────────────────────────────
    const confEl = document.getElementById('ai-signal-confidence');
    if (confEl) {
      confEl.textContent = `${confidence.toFixed(1)}%`;
    }

    // ── Síntese ─────────────────────────────────────────────────────────────
    const synthEl = document.getElementById('ai-signal-synthesis');
    if (synthEl) {
      synthEl.textContent = synthesis;
    }

    // ── Card container ──────────────────────────────────────────────────────
    const card = document.getElementById('ai-signal-card');
    if (card) {
      card.className = card.className
        .replace(/signal--(bullish|bearish|neutral)/gi, '')
        .trim();
      card.classList.add(signalClasses[signal] || 'signal--neutral');

      // Micro-animação: pisca o card para indicar atualização
      card.classList.add('signal--updated');
      setTimeout(() => card.classList.remove('signal--updated'), 600);
    }

    console.debug(`[TradeWS] Sinal atualizado — ${data.ticker} | ${signal} | ${confidence.toFixed(1)}%`);
  }

  /**
   * Atualiza o indicador de status de conexão no DOM.
   *
   * @param {'connected'|'disconnected'|'reconnecting'} status
   */
  function setStatus(status) {
    const el = document.getElementById('ai-ws-status');
    if (!el) return;

    const labels = {
      connected:    '● Ao vivo',
      disconnected: '○ Desconectado',
      reconnecting: '◌ Reconectando…',
    };
    el.textContent = labels[status] || status;
    el.dataset.wsStatus = status;
  }

  // ── WebSocket ─────────────────────────────────────────────────────────────

  /**
   * Inicia o heartbeat (ping) para manter a conexão viva.
   */
  function startPing() {
    stopPing();
    pingTimer = setInterval(() => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: 'ping' }));
      }
    }, PING_INTERVAL);
  }

  /**
   * Para o heartbeat.
   */
  function stopPing() {
    if (pingTimer) {
      clearInterval(pingTimer);
      pingTimer = null;
    }
  }

  /**
   * Calcula o delay de reconexão com back-off exponencial.
   *
   * @param {number} attempt - Número de tentativas já realizadas.
   * @returns {number} Delay em milissegundos.
   */
  function backoffDelay(attempt) {
    const delay = BASE_DELAY_MS * Math.pow(2, attempt);
    // Adiciona jitter de ±20% para evitar thundering herd
    const jitter = delay * 0.2 * (Math.random() * 2 - 1);
    return Math.min(delay + jitter, MAX_DELAY_MS);
  }

  /**
   * Abre a conexão WebSocket para o ticker informado.
   *
   * @param {string} assetTicker - Ticker do ativo (ex.: 'PETR4').
   */
  function connect(assetTicker) {
    ticker = assetTicker.toUpperCase();

    const url = `${WS_SCHEME}://${window.location.host}/ws/asset/${ticker}/`;
    console.info(`[TradeWS] Conectando a ${url} (tentativa ${retries + 1}/${MAX_RETRIES})`);

    try {
      socket = new WebSocket(url);
    } catch (err) {
      console.error('[TradeWS] Falha ao criar WebSocket:', err);
      scheduleReconnect();
      return;
    }

    // ── Handlers ──────────────────────────────────────────────────────────

    socket.onopen = () => {
      console.info(`[TradeWS] Conexão estabelecida — ${ticker}`);
      retries = 0;
      setStatus('connected');
      startPing();
    };

    socket.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        console.warn('[TradeWS] Payload não-JSON recebido:', event.data);
        return;
      }

      if (data.type === 'pong') return; // heartbeat response — ignora

      if (data.type === 'ai_signal') {
        updateSignalCard(data);
      }
    };

    socket.onerror = (error) => {
      console.error('[TradeWS] Erro de WebSocket:', error);
    };

    socket.onclose = (event) => {
      stopPing();
      console.warn(`[TradeWS] Conexão fechada — code=${event.code}, reason="${event.reason}"`);

      // Código 4003 = ticker inválido (rejeitado pelo servidor) — não reconectar
      if (event.code === 4003) {
        console.error('[TradeWS] Ticker inválido — reconexão cancelada.');
        setStatus('disconnected');
        return;
      }

      scheduleReconnect();
    };
  }

  /**
   * Agenda reconexão com back-off exponencial.
   */
  function scheduleReconnect() {
    if (retries >= MAX_RETRIES) {
      console.error('[TradeWS] Número máximo de tentativas atingido — conexão encerrada.');
      setStatus('disconnected');
      return;
    }

    const delay = backoffDelay(retries);
    retries += 1;
    setStatus('reconnecting');
    console.info(`[TradeWS] Reconectando em ${Math.round(delay / 1000)}s… (tentativa ${retries}/${MAX_RETRIES})`);

    reconnectTimer = setTimeout(() => connect(ticker), delay);
  }

  /**
   * Fecha a conexão WebSocket e limpa os timers.
   */
  function disconnect() {
    stopPing();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (socket) {
      socket.onclose = null; // evita reconexão automática ao fechar manualmente
      socket.close();
      socket = null;
    }
    setStatus('disconnected');
  }

  // ── Auto-inicialização ─────────────────────────────────────────────────────
  // Se existir um elemento com data-ticker no DOM, conecta automaticamente.

  document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('ws-ticker');
    if (el && el.dataset.ticker) {
      connect(el.dataset.ticker);
    }
  });

  // ── API pública ────────────────────────────────────────────────────────────
  return { connect, disconnect };
})();
