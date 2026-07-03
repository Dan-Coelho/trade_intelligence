# ANTIGRAVITY.md — Trade Intelligence B3

> Instruções de contexto do agente para o projeto. Este arquivo é lido automaticamente e define como o assistente deve se comportar em todas as interações com este codebase.

---

## Identidade do Projeto

**Nome:** Trade Intelligence B3
**Tipo:** Web app Django full-stack — dashboard preditivo para traders da B3
**Estado atual:** Sprint 0 concluída parcialmente — scaffold Django criado, zero código de negócio implementado
**Documentação de referência:**
- `PRD.md` — escopo completo, requisitos e sprints
- `TASKS.md` — checklist de progresso por sprint
- `docs/architecture.md` — stack e estrutura de apps
- `docs/code-standards.md` — regras obrigatórias de código
- `docs/design-system.md` — paleta, tipografia, componentes TailwindCSS

---

## O que o Agente Deve Saber

### Propósito do sistema
Centralizar análise de ativos da B3 (ações + futuros WIN/WDO) em um único dashboard. O sistema emite sinais direcionais **Bullish / Bearish / Neutro** com percentual de confiança e justificativa gerada por um sistema multi-agente LangGraph, combinando:
- Análise técnica (RSI, MACD, Bollinger Bands, padrões TA-Lib, Fibonacci)
- Análise fundamentalista (P/L, ROE, DY, EV/EBITDA — apenas para ações)
- Dados macroeconômicos (SELIC, IPCA, PIB via API BCB)
- Sentimento de notícias (Investing.com scraping + NewsAPI fallback)

### O que NÃO existe no projeto ainda
Antes de modificar qualquer arquivo, assuma que **nenhum app tem código de negócio**. Todos os 10 apps (`accounts`, `ai_agents`, `analysis`, `backtest`, `dashboard`, `fundamentals`, `market_data`, `news`, `risk`, `watchlist`) contêm apenas o scaffold gerado pelo `django-admin startapp`. Os arquivos `urls.py`, `forms.py`, `tasks.py`, `signals.py`, `consumers.py`, `utils.py` **não existem em nenhum app** — precisam ser criados.

### Módulo de configuração Django
O projeto usa `core/` como pacote de configuração (não como app de negócio):
- `DJANGO_SETTINGS_MODULE = 'core.settings'`
- `ROOT_URLCONF = 'core.urls'`
- `WSGI_APPLICATION = 'core.wsgi.application'`

---

## Regras de Código (Não Negociáveis)

O agente deve aplicar estas regras em **todo código que gerar ou modificar**. Desvios só são permitidos com justificativa explícita em comentário no próprio código.

### Python
- Código 100% em inglês: classes, variáveis, funções, nomes de arquivo
- PEP 8 estrito — use `ruff` para verificação
- Aspas simples em todo código Python
  ```python
  # ✅
  ticker = 'PETR4'
  # ❌
  ticker = "PETR4"
  ```

### Views
- Exclusivamente **Class-Based Views (CBVs)**
- `LoginRequiredMixin` como primeiro mixin em qualquer view protegida
- Nenhuma function-based view, salvo exceção documentada
  ```python
  class DashboardView(LoginRequiredMixin, TemplateView):
      template_name = 'dashboard/index.html'
  ```

### Formulários
- Todo formulário herda de `forms.Form` ou `forms.ModelForm`
- Validação customizada sempre no método `clean()` ou `clean_<campo>()`

### Models
- Todos os models obrigatoriamente com:
  ```python
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)
  ```
- Choices definidos como constantes de classe antes dos campos
- `__str__` implementado em todo model

### Signals
- Arquivo: `signals.py` dentro do app — nunca em `models.py` ou `apps.py`
- Registrado em `AppConfig.ready()` via `import <app>.signals`

### Celery Tasks
- Arquivo: `tasks.py` dentro do app responsável pela operação
- Tasks com I/O externo: `autoretry_for=(Exception,)`, `max_retries=3`, `default_retry_delay=60`

### URLs
- Cada app tem seu próprio `urls.py`
- `core/urls.py` apenas agrega com `include()`

### Secrets
- Nunca hardcoded — lidos via `python-decouple` do `.env`
- `.env` está no `.gitignore` e nunca é versionado

### Interface
- Todo texto visível ao usuário em **Português Brasileiro (PT-BR)**
- Labels, mensagens de erro, placeholders, notificações — tudo em PT-BR

---

## Arquitetura de Apps

| App | Responsabilidade |
|---|---|
| `core/` | `settings.py`, `urls.py` raiz — **não é um app Django, é o pacote de config** |
| `accounts` | Cadastro, login, logout via Django Allauth |
| `market_data` | Models `Asset` e `OHLCCandle`; tasks de coleta OHLC (Brapi.dev, yfinance) |
| `analysis` | RSI, MACD, Bollinger Bands, padrões TA-Lib, Fibonacci; dispara `run_ai_analysis` via signal |
| `ai_agents` | Grafo LangGraph: Supervisor → [Technical Agent, Fundamental Agent, Macro/News Agent] → Synthesis Node → `AISignal` |
| `backtest` | `backtesting.py`, model `BacktestResult` |
| `risk` | ATR, stop loss sugerido, position sizing Kelly simplificado |
| `news` | Scraping Investing.com + fallback NewsAPI, model `NewsArticle`, sentimento via LLM |
| `fundamentals` | Scraping Fundamentus + Brapi.dev, model `FundamentalData` |
| `watchlist` | Models `Watchlist` e `PriceAlert`; task de monitoramento de alertas de preço |
| `dashboard` | `DashboardView`, consumers WebSocket, todos os templates principais |

---

## Models Planejados (ainda não implementados)

O agente deve usar estes schemas ao criar os models. Todos os models abaixo ainda precisam ser escritos.

| Model | App | Campos-chave |
|---|---|---|
| `Asset` | `market_data` | `ticker (unique)`, `name`, `asset_type (STOCK/FUTURE)`, `exchange` |
| `OHLCCandle` | `market_data` | FK `asset`, `timeframe`, `timestamp`, `open/high/low/close`, `volume`; `unique_together: (asset, timestamp, timeframe)` |
| `TechnicalIndicator` | `analysis` | FK `asset`, `indicator_name`, `timeframe`, `timestamp`, `values (JSONField)` |
| `CandlestickPattern` | `analysis` | FK `asset`, `pattern_name`, `timeframe`, `timestamp`, `direction (BULLISH/BEARISH/NEUTRAL)`, `confidence` |
| `FundamentalData` | `fundamentals` | FK `asset`, `reference_date`, `pl_ratio`, `roe`, `dividend_yield`, `ev_ebitda`, `raw_data (JSONField)` |
| `MacroIndicator` | `news` | `name`, `source`, `reference_date`, `value`, `unit` |
| `NewsArticle` | `news` | FK `asset (null=True)`, `title`, `body`, `source_url`, `source_name`, `sentiment`, `sentiment_score`, `published_at` |
| `AISignal` | `ai_agents` | FK `asset`, `signal_type (BULLISH/BEARISH/NEUTRAL)`, `confidence_pct`, `technical_justification`, `fundamental_justification`, `macro_justification`, `synthesis_text`, `timeframe`, `generated_at` |
| `BacktestResult` | `backtest` | FK `user`, FK `asset`, `strategy_name`, `start_date`, `end_date`, `initial_capital`, `final_capital`, `win_rate`, `sharpe_ratio`, `max_drawdown`, `trades_log (JSONField)` |
| `Watchlist` | `watchlist` | FK `user`, FK `asset`, `display_order`; `unique_together: (user, asset)` |
| `PriceAlert` | `watchlist` | FK `user`, FK `asset`, `condition (ABOVE/BELOW)`, `target_price`, `is_active`, `is_triggered`, `triggered_at (null=True)` |
| `RiskCalculation` | `risk` | FK `user`, FK `asset`, `atr_value`, `suggested_stop_loss`, `user_capital`, `position_size`, `kelly_fraction` |

---

## Fontes de Dados e Tasks Celery

| Task | App | Frequência | Fonte |
|---|---|---|---|
| `fetch_intraday_ohlc` | `market_data` | 1 min (pregão) | Brapi.dev / TrydAPI |
| `fetch_daily_ohlc` | `market_data` | 1h (pregão) | yfinance |
| `fetch_macro_data` | `news` | 2h | API BCB (série 432 SELIC, 433 IPCA) |
| `fetch_fundamentals` | `fundamentals` | 24h | Fundamentus (scraping) + Brapi.dev |
| `fetch_news` | `news` | 24h | Investing.com (scraping) → fallback NewsAPI |
| `run_technical_analysis` | `analysis` | pós-insert OHLCCandle | Disparada por signal `post_save` |
| `run_ai_analysis` | `ai_agents` | pós-insert TechnicalIndicator | Disparada por signal `post_save` |
| `check_price_alerts` | `watchlist` | 1 min | Consulta banco, compara com último preço |

---

## Pipeline de Dados (fluxo completo)

```
Celery Beat
  ├── fetch_intraday_ohlc / fetch_daily_ohlc
  │     └── insere OHLCCandle
  │           └── signal post_save → run_technical_analysis.delay(asset_id)
  │                 └── insere TechnicalIndicator
  │                       └── signal post_save → run_ai_analysis.delay(asset_id)
  │                             └── LangGraph executa agentes
  │                                   └── insere AISignal
  │                                         └── Django Channels publica no grupo ws/asset/<ticker>/
  │                                               └── Dashboard atualizado via WebSocket
  ├── fetch_macro_data → insere MacroIndicator
  ├── fetch_fundamentals → insere FundamentalData
  └── fetch_news → insere NewsArticle (com sentimento via LLM)
```

---

## Sistema Multi-Agente LangGraph

O grafo reside em `ai_agents/graph.py`. O estado compartilhado (`AgentState`) é um `TypedDict` com os campos:

```python
class AgentState(TypedDict):
    ticker: str
    asset_type: str          # 'STOCK' ou 'FUTURE'
    technical_analysis: str
    fundamental_analysis: str
    macro_analysis: str
    signal: str              # 'BULLISH' | 'BEARISH' | 'NEUTRAL'
    confidence: float
    synthesis: str
```

**Roteamento:** `Supervisor` decide quais agentes acionar baseado em `asset_type`:
- `FUTURE` → Technical Agent + Macro/News Agent
- `STOCK` → Technical Agent + Fundamental Agent + Macro/News Agent

**Cache Redis:** resultado do sinal é cacheado por `ai_signal_{asset_id}` com TTL de 300 segundos antes de chamar o LangGraph.

---

## Design System — Referência Rápida

### Fundo da página
```html
<div class="min-h-screen bg-[#0A0E1A] text-gray-50 font-sans">
```

### Card padrão
```html
<div class="bg-gray-900 border border-gray-700/50 rounded-xl p-5 shadow-lg">
```

### Botão primário
```html
<button class="bg-blue-500 hover:bg-blue-600 text-white font-semibold px-4 py-2 rounded-lg transition-colors duration-200">
```

### Input padrão
```html
<input class="bg-gray-800 border border-gray-700 text-gray-100 placeholder-gray-500 rounded-lg px-3 py-2 text-sm w-full focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all duration-200">
```

### Cores dos sinais
```html
<!-- Bullish -->  <span class="text-emerald-400">🟢 Alta</span>
<!-- Bearish -->  <span class="text-red-400">🔴 Baixa</span>
<!-- Neutro  -->  <span class="text-gray-400">⚪ Neutro</span>
```

---

## Restrições Absolutas (o agente nunca deve fazer)

- ❌ Propor ou instalar dependências não listadas no `pyproject.toml` ou no PRD sem aprovação explícita
- ❌ Criar function-based views sem justificativa documentada no código
- ❌ Escrever texto visível ao usuário em inglês (templates, labels, mensagens de erro)
- ❌ Definir signals fora de `signals.py`
- ❌ Hardcodar `SECRET_KEY`, `API_KEY` ou qualquer secret no código-fonte
- ❌ Adicionar Docker, testes automatizados ou configuração de produção antes das sprints 8 e 9
- ❌ Criar models sem `created_at` e `updated_at`
- ❌ Usar aspas duplas em strings Python quando aspas simples são suficientes
- ❌ Criar URLs de app diretamente em `core/urls.py` — cada app tem seu próprio `urls.py`
- ❌ Ignorar o TASKS.md — sempre verificar o que está marcado antes de propor trabalho já concluído

---

## Banco de Dados por Fase

| Sprint | Banco |
|---|---|
| 0–4 | SQLite (nativo Django, `db.sqlite3` na raiz) |
| 5+ | PostgreSQL 16 + TimescaleDB 2.x (`OHLCCandle` como hypertable) |
| 8–9 | Docker + nginx + Gunicorn + Daphne |

---

## Variáveis de Ambiente Esperadas

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Chave secreta Django |
| `DEBUG` | `True` dev / `False` prod |
| `ALLOWED_HOSTS` | Hosts separados por vírgula |
| `LLM_PROVIDER` | `gemini` ou `openai` |
| `LLM_API_KEY` | Chave da API do LLM |
| `REDIS_URL` | `redis://localhost:6379/0` |

---

## Como Consultar o Progresso

Antes de implementar qualquer coisa, consulte `TASKS.md`:
- Itens marcados com `[x]` — concluídos, não reimplementar
- Itens marcados com `[ ]` — pendentes, próximas tarefas a implementar
- Siga a ordem das sprints — não pule sprints sem confirmar com o usuário
