# Arquitetura — Trade Intelligence B3

---

## Visão Geral

Aplicação web Django full-stack para análise preditiva de ativos da B3 (ações e contratos futuros WIN/WDO). O sistema emite sinais direcionais (Bullish / Bearish / Neutro) combinando análise técnica, dados macroeconômicos e sentimento de notícias.

---

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Backend | Django 5.x |
| Task Queue | Celery 5.x + Redis 7.x |
| Banco (desenvolvimento) | SQLite (nativo Django) |
| Real-time | Django Channels 4.x + WebSocket |
| Agentes IA | LangGraph + LangChain |
| LLM | Gemini 1.5 Pro ou GPT-4o (configurável via `LLM_PROVIDER` no `.env`) |
| Frontend — gráficos | TradingView Lightweight Charts 4.x |
| Frontend — interatividade | HTMX 2.x + Alpine.js 3.x |
| CSS | TailwindCSS 3.x |
| Análise Técnica | TA-Lib + pandas-ta |
| Backtest | backtesting.py |
| Autenticação | Django Allauth |
| HTTP / Scraping | httpx + BeautifulSoup4 |

---

## Estrutura de Diretórios

```
trade_indicator/              ← Raiz do projeto
├── core/                     ← Configuração Django (settings.py, urls.py, wsgi.py, asgi.py)
├── accounts/                 ← Autenticação (integra Django Allauth)
├── market_data/              ← Models de ativos e candles OHLC, tasks de coleta
├── analysis/                 ← Indicadores técnicos, padrões de candlestick, Fibonacci
├── ai_agents/                ← Workflows LangGraph, agentes, synthesis node
├── backtest/                 ← Engine de backtest, models de resultado
├── risk/                     ← Position sizing (Kelly), stop loss (ATR)
├── news/                     ← Scraping de notícias, classificação de sentimento
├── fundamentals/             ← Dados fundamentalistas (Fundamentus + Brapi.dev)
├── watchlist/                ← Watchlist e alertas de preço por usuário
├── dashboard/                ← Views principais, consumers WebSocket, templates
├── docs/                     ← Esta documentação
├── manage.py
├── pyproject.toml
├── PRD.md                    ← Product Requirements Document
└── TASKS.md                  ← Checklist de sprints
```

### Responsabilidade de cada app

| App | Responsabilidade |
|---|---|
| `core` | `settings.py`, `urls.py` raiz, `wsgi.py`, `asgi.py` |
| `accounts` | Cadastro, login, logout via Django Allauth |
| `market_data` | Models `Asset` e `OHLCCandle`; tasks Celery de coleta de OHLC |
| `analysis` | Cálculo de RSI, MACD, Bollinger Bands, padrões TA-Lib, Fibonacci |
| `ai_agents` | Grafo LangGraph com Technical Agent, Fundamental Agent, Macro/News Agent e Synthesis Node |
| `backtest` | Execução de `backtesting.py`, model `BacktestResult` |
| `risk` | Cálculo de ATR, stop loss sugerido e position sizing (Kelly simplificado) |
| `news` | Scraping Investing.com (fallback NewsAPI), model `NewsArticle`, sentimento via LLM |
| `fundamentals` | Scraping Fundamentus + Brapi.dev, model `FundamentalData` |
| `watchlist` | Models `Watchlist` e `PriceAlert`; task de monitoramento de alertas |
| `dashboard` | `DashboardView`, consumers WebSocket, templates principais |

---

## Configuração Django

O módulo de configuração do Django é `core` (não um app). O `DJANGO_SETTINGS_MODULE` aponta para `core.settings`.

```
WSGI_APPLICATION = 'core.wsgi.application'
ROOT_URLCONF      = 'core.urls'
```

Todos os apps estão registrados em `INSTALLED_APPS` no `core/settings.py`.

---

## Variáveis de Ambiente

Definidas no arquivo `.env` na raiz (não versionado). As chaves esperadas são:

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave secreta do Django |
| `DEBUG` | `True` em desenvolvimento, `False` em produção |
| `ALLOWED_HOSTS` | Lista de hosts permitidos |
| `LLM_PROVIDER` | `gemini` ou `openai` |
| `LLM_API_KEY` | Chave da API do LLM selecionado |
| `REDIS_URL` | URL de conexão com o Redis (broker do Celery) |

> O `settings.py` atual ainda não lê o `.env` via `python-decouple`. Isso é uma tarefa pendente (Sprint 0, tarefa 0.1.5).

---

## Fluxo de Dados (planejado)

```
Celery Beat → tasks de coleta (OHLC, macro, notícias, fundamentais)
           ↓
      PostgreSQL / SQLite
           ↓
  Signal post_save em OHLCCandle → task run_technical_analysis
           ↓
  Signal post_save em TechnicalIndicator → task run_ai_analysis (LangGraph)
           ↓
  AISignal salvo + publicado via Django Channels WebSocket
           ↓
      Dashboard atualizado em tempo real
```
