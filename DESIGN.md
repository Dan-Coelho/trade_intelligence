# 📊 Trade Intelligence B3 — Documento de Design

> Gerado em: 2026-06-27 | Brainstorming validado e confirmado pelo usuário.

---

## 1. Understanding Summary

- **O que está sendo construído**: Web app Django com dashboard preditivo para traders de Mini Índice (WIN), Mini Dólar (WDO) e ações avulsas da B3
- **Por que existe**: Antecipar movimentos de mercado combinando análise técnica, fundamentalista, macroeconômica e IA multi-agente
- **Para quem**: MVP para uso pessoal → evolução para SaaS multi-tenant
- **Objetivo primário**: Dashboard de análise preditiva para auxiliar decisões **manuais** do trader (IA como co-piloto)
- **Resultado principal**: Sinal Bullish / Bearish / Neutro com justificativa multi-dimensional

### Não-Objetivos (MVP)
- ❌ Execução automática de ordens
- ❌ App mobile nativo
- ❌ Cobertura de FIIs, BDRs, opções

---

## 2. Escopo de Ativos

| Tipo | Ativos | Observação |
|---|---|---|
| Contratos Futuros | WIN (Mini Índice), WDO (Mini Dólar) | OHLC intraday, sem fundamentalismo |
| Ações | Qualquer ticker da B3 (busca livre) | OHLC + fundamentalistas + IA |

---

## 3. Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Backend | Django 5.x |
| Task Queue | Celery + Redis (broker + cache) |
| Banco principal | PostgreSQL + TimescaleDB (hypertables para OHLC) |
| Real-time | Django Channels + WebSocket |
| Agentes IA | LangGraph + LangChain |
| LLM | Gemini 1.5 Pro ou GPT-4o (configurável) |
| Frontend | HTMX + Alpine.js + TradingView Lightweight Charts |
| Multi-tenant | django-tenants (schema isolation) |
| Autenticação | Django Allauth + JWT (simplejwt) |
| Análise Técnica | TA-Lib + pandas-ta |
| Backtest Engine | backtesting.py |

---

## 4. Fontes de Dados

| Dado | Fonte | Frequência | Custo |
|---|---|---|---|
| OHLC Intraday (WIN/WDO) | Brapi.dev / TrydAPI | A cada 1 min | Freemium |
| OHLC Diário (ações) | yfinance | A cada 1h (pregão) | Gratuito |
| Dados Macroeconômicos | API Banco Central (BCB) | A cada 2h | Gratuito |
| Dados Fundamentalistas | Fundamentus (scraping) + Brapi.dev | A cada 24h | Gratuito |
| Notícias | Investing.com (scraping) + NewsAPI | A cada 24h | Gratuito/Freemium |

> ⚠️ Investing.com não possui API pública. Coleta via `httpx` + `BeautifulSoup` com rate limiting e retry logic no Celery.

---

## 5. Arquitetura — Monolito Modular Django

```
trade_intelligence/
├── core/              → auth, multi-tenant, settings
├── market_data/       → modelos OHLC, Celery tasks de coleta
├── analysis/          → indicadores técnicos, padrões, Fibonacci
├── ai_agents/         → LangGraph workflows, tools, supervisor
├── backtest/          → engine de simulação de estratégias
├── risk/              → position sizing, stop loss, ATR
├── news/              → scraping Investing.com, sentimento
├── fundamentals/      → scraping Fundamentus, scoring
└── dashboard/         → views, WebSocket consumers, templates
```

---

## 6. Fluxo de Dados

```
CELERY BEAT SCHEDULER
├── 1min   → coleta OHLC intraday (WIN/WDO)
├── 1h     → coleta OHLC diário (ações, horário de pregão)
├── 2h     → dados macro BCB
├── 24h    → fundamentalistas (Fundamentus + Brapi)
└── 24h    → notícias (Investing.com + NewsAPI)
        │
        ▼ publica no Redis
CELERY WORKERS (3 filas)
├── [market_data]   → yfinance, Brapi, TrydAPI
├── [fundamentals]  → Fundamentus scraper, Brapi
└── [news_macro]    → Investing.com scraper, BCB API
        │
        ▼ persiste
PostgreSQL + TimescaleDB
├── hypertable: ohlc_candles (ticker, time, OHLCV)
├── table: fundamentals (ticker, date, metrics JSONB)
├── table: macro_indicators (name, date, value)
└── table: news_articles (ticker, title, body, sentiment)
        │
        ▼ após inserção → dispara análise
ANALYSIS ENGINE (Celery post-insert task)
├── Indicadores técnicos (RSI, MACD, Bollinger)
├── Padrões gráficos (TA-Lib)
├── Níveis de Fibonacci
└── Dispara LangGraph Agent se padrão relevante
        │
        ▼
WebSocket → Dashboard (tempo real)
```

---

## 7. Agentes LangGraph

### Supervisor Agent (StateGraph)
- Recebe: ticker + contexto do usuário
- Decide quais agentes acionar com base no tipo de ativo

### Agente 1 — Technical Agent
```python
tools = [
    get_ohlc_candles(ticker, timeframe),
    detect_candlestick_patterns(ticker),   # TA-Lib
    calculate_fibonacci_levels(ticker),
    run_backtest(ticker, strategy),
    get_indicators(ticker),                # RSI, MACD, Bollinger
]
```

### Agente 2 — Fundamental Agent *(apenas ações)*
```python
tools = [
    get_fundamentals(ticker),             # P/L, ROE, DY, EV/EBITDA
    compare_sector_peers(ticker),
    get_valuation_score(ticker),
]
```

### Agente 3 — Macro/News Agent
```python
tools = [
    get_macro_indicators(),               # SELIC, IPCA, PIB
    get_news_sentiment(ticker),           # LLM classifica bullish/bearish
    get_market_risk_score(),
]
```

### Synthesis Node
- Consolida análises dos 3 agentes
- Gera sinal: 🟢 Bullish | 🔴 Bearish | ⚪ Neutro
- Inclui % de confiança e justificativa textual

---

## 8. Interface — Dashboard

### Layout Principal
- **Header**: Busca de ticker, Watchlist, Alertas, Perfil
- **Painel esquerdo**: Gráfico TradingView Lightweight Charts (candlestick + Fibonacci + Bollinger + MACD/RSI)
- **Painel direito**:
  - Sinal IA (Bullish/Bearish/Neutro + confiança + motivos)
  - Dados fundamentalistas (para ações)
- **Rodapé**: Indicadores macro em tempo real + últimas notícias

### Funcionalidades
| Feature | Descrição |
|---|---|
| Gráfico interativo | Candlestick OHLC com overlay de indicadores e padrões |
| Sinal IA | Bullish/Bearish/Neutro com justificativa multi-agente |
| Painel de Backtest | Período, estratégia, capital → Win Rate, Sharpe, Drawdown |
| Chat IA | Perguntas livres sobre o ativo com contexto dos dados reais |
| Gestão de Risco | Stop Loss (ATR), Position Sizing (Kelly simplificado) |

---

## 9. Multi-Tenant

- **Biblioteca**: `django-tenants`
- **Isolamento**: Schema PostgreSQL por tenant
- **Dados compartilhados** (schema `public`): OHLC, macro, notícias
- **Dados isolados por tenant**: watchlist, alertas, backtests, configurações de risco

---

## 10. Segurança

| Item | Solução |
|---|---|
| Autenticação | Django Allauth (e-mail + senha) |
| API interna | JWT via djangorestframework-simplejwt |
| Rate limiting | django-ratelimit por tenant |
| Segredos | .env + Django Secrets |
| HTTPS | nginx + Let's Encrypt (produção) |

---

## 11. Decision Log

| # | Decisão | Alternativas Consideradas | Motivo |
|---|---|---|---|
| 1 | Arquitetura Monolito Modular | Microserviços, Django+FastAPI | Menor complexidade no MVP, boundaries claros para extração futura |
| 2 | TimescaleDB para OHLC | InfluxDB, MongoDB | Extensão nativa do Postgres, queries SQL familiares, sem novo infra |
| 3 | LangGraph com 3 agentes especializados + Supervisor | Único agente genérico | Separação de responsabilidades, cada agente tem contexto focado |
| 4 | Investing.com via scraping | API paga, RSS | Sem API pública; Celery task isolada com rate limit e retry |
| 5 | Notícias e fundamentalistas a cada 24h | Mais frequente | Dados mudam lentamente; evita sobrecarga de scraping |
| 6 | Macro a cada 2h | 24h | BCB pode publicar atualizações ao longo do dia |
| 7 | django-tenants para multi-tenancy | Row-level isolation, subdomain apps | Schema isolation é mais seguro e performático para SaaS |
| 8 | backtesting.py como engine | Zipline, Backtrader | Mais leve, sem dependências complexas, suficiente para MVP |
| 9 | TradingView Lightweight Charts | Chart.js, Plotly, D3 | Biblioteca específica para trading, UX profissional, gratuita |
| 10 | Busca livre por ticker (ações) | Lista fixa, cobertura IBOV | Flexibilidade máxima para o trader |

---

## 12. Premissas Documentadas

- 🔶 Servidor Linux (VPS/Cloud) para Celery + Redis + PostgreSQL
- 🔶 LLM configurável: GPT-4o ou Gemini 1.5 Pro
- 🔶 Intraday WIN/WDO via Brapi/TrydAPI pode exigir plano pago em produção
- 🔶 Backtest é simulado (não conectado a corretora para ordens reais no MVP)
- 🔶 Investing.com pode bloquear scraping — fallback para NewsAPI

---

## 13. Riscos Conhecidos

| Risco | Mitigação |
|---|---|
| Bloqueio do scraping (Investing.com) | Fallback para NewsAPI; User-Agent rotation; rate limiting |
| Latência do LLM nos agentes | Cache de resultados no Redis por N minutos |
| Rollover de contratos WIN/WDO | Lógica de rollover automático no market_data app |
| Escala de séries temporais | TimescaleDB com compressão automática de dados antigos |
| Custo do LLM em produção SaaS | Cache agressivo + limitar chamadas por tenant/dia |

---

*Documento gerado após sessão de brainstorming estruturada. Pronto para handoff de implementação.*
