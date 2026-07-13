## Lista de Tarefas por Sprint

### 🏃 Sprint 0 — Setup e Fundação do Projeto

- [x] **0.1 — Configuração do Ambiente**
  - [x] 0.1.1 Criar virtualenv Python 3.12 e arquivo `requirements.txt` inicial
  - [x] 0.1.2 Instalar Django 5.x, django-allauth, celery, redis, channels, htmx
  - [x] 0.1.3 Criar projeto Django: `django-admin startproject core .`
  - [x] 0.1.4 Criar arquivo `.env` com variáveis: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `LLM_PROVIDER`, `LLM_API_KEY`, `REDIS_URL`
  - [x] 0.1.5 Configurar `settings.py` com `python-decouple` para ler `.env`
  - [x] 0.1.6 Configurar `LANGUAGE_CODE = 'pt-br'` e `TIME_ZONE = 'America/Sao_Paulo'`
  - [x] 0.1.7 Criar `.gitignore` com `.env`, `db.sqlite3`, `__pycache__`, `node_modules`

- [x] **0.2 — Estrutura de Apps**
  - [x] 0.2.1 Criar app `core`: `python manage.py startapp core`
  - [x] 0.2.2 Criar app `accounts`: `python manage.py startapp accounts`
  - [x] 0.2.3 Criar app `market_data`: `python manage.py startapp market_data`
  - [x] 0.2.4 Criar app `analysis`: `python manage.py startapp analysis`
  - [x] 0.2.5 Criar app `ai_agents`: `python manage.py startapp ai_agents`
  - [x] 0.2.6 Criar app `backtest`: `python manage.py startapp backtest`
  - [x] 0.2.7 Criar app `risk`: `python manage.py startapp risk`
  - [x] 0.2.8 Criar app `news`: `python manage.py startapp news`
  - [x] 0.2.9 Criar app `fundamentals`: `python manage.py startapp fundamentals`
  - [x] 0.2.10 Criar app `watchlist`: `python manage.py startapp watchlist`
  - [x] 0.2.11 Criar app `dashboard`: `python manage.py startapp dashboard`
  - [x] 0.2.12 Registrar todos os apps em `INSTALLED_APPS` no `settings.py`

- [x] **0.3 — TailwindCSS e Assets Estáticos**
  - [x] 0.3.1 Configurar `STATICFILES_DIRS` e `STATIC_URL` no `settings.py`
  - [x] 0.3.2 Criar `static/css/main.css` com import do TailwindCSS via CDN (dev)
  - [x] 0.3.3 Criar `static/css/design_system.css` com variáveis CSS customizadas (paleta de cores)
  - [x] 0.3.4 Criar `static/js/htmx.min.js` e `static/js/alpine.min.js` (download local)
  - [x] 0.3.5 Criar diretório `templates/` na raiz e configurar `TEMPLATES[0]['DIRS']`

- [x] **0.4 — Template Base**
  - [x] 0.4.1 Criar `templates/base.html` com: `<head>` com meta charset/viewport, link para Inter (Google Fonts), TailwindCSS CDN, Alpine.js, HTMX; `<body class="bg-[#0A0E1A] text-gray-50 font-sans">`; blocks: `title`, `extra_head`, `content`, `extra_js`
  - [x] 0.4.2 Criar `templates/partials/navbar.html` com logo, busca, links de autenticação
  - [x] 0.4.3 Criar `templates/partials/footer.html` com rodapé informativo simples

---

### 🏃 Sprint 1 — Autenticação e Landing Page

- [x] **1.1 — Configuração do Django Allauth**
  - [x] 1.1.1 Instalar e configurar `django-allauth` no `settings.py` (AUTHENTICATION_BACKENDS, INSTALLED_APPS, SITE_ID)
  - [x] 1.1.2 Adicionar `path('accounts/', include('allauth.urls'))` no `urls.py` raiz
  - [x] 1.1.3 Configurar `LOGIN_REDIRECT_URL = '/dashboard/'` e `LOGOUT_REDIRECT_URL = '/'`
  - [x] 1.1.4 Configurar `ACCOUNT_EMAIL_REQUIRED = True`, `ACCOUNT_USERNAME_REQUIRED = False`, `ACCOUNT_AUTHENTICATION_METHOD = 'email'`

- [x] **1.2 — Templates de Autenticação**
  - [x] 1.2.1 Criar `templates/account/login.html` — formulário de login com design dark mode, campos e-mail e senha, botão "Entrar", link "Esqueci minha senha" e link "Cadastre-se"
  - [x] 1.2.2 Criar `templates/account/signup.html` — formulário de cadastro com campos nome, e-mail, senha, confirmação de senha, botão "Criar conta"
  - [x] 1.2.3 Criar `templates/account/password_reset.html` — formulário de recuperação de senha
  - [x] 1.2.4 Criar `templates/account/email_confirm.html` — página de confirmação de e-mail
  - [x] 1.2.5 Aplicar design system (dark mode, paleta azul/ciano, Inter) em todos os templates de auth

- [x] **1.3 — Landing Page Pública**
  - [x] 1.3.1 Criar CBV `LandingPageView(TemplateView)` em `core_app/views.py`
  - [x] 1.3.2 Adicionar lógica de redirecionamento: se `request.user.is_authenticated`, redirecionar para `/dashboard/`
  - [x] 1.3.3 Registrar URL `path('', LandingPageView.as_view(), name='landing')` em `core_app/urls.py`
  - [x] 1.3.4 Incluir `core_app/urls.py` no `urls.py` raiz
  - [x] 1.3.5 Criar `templates/core_app/landing.html` — seções: Hero com headline, sub-headline, CTAs "Cadastre-se" e "Login"; Features (3 cards de funcionalidade); Footer
  - [x] 1.3.6 Estilizar `landing.html` com gradiente de fundo `from-[#0A0E1A] via-[#1E3A5F] to-[#0A0E1A]`, animações CSS sutis, design premium

- [x] **1.4 — Middleware de Autenticação**
  - [x] 1.4.1 Configurar `LoginRequiredMixin` como mixin padrão para todas as CBVs do dashboard (será aplicado nas sprints seguintes)
  - [x] 1.4.2 Testar manualmente: acesso a `/dashboard/` sem login redireciona para `/accounts/login/`

---

### 🏃 Sprint 2 — Models de Dados Core

- [x] **2.1 — App `market_data` — Models**
  - [x] 2.1.1 Criar `market_data/models.py` com model `Asset`: campos `ticker (CharField, unique)`, `name (CharField)`, `asset_type (CharField, choices: FUTURE/STOCK)`, `exchange (CharField, default='B3')`, `created_at`, `updated_at`
  - [x] 2.1.2 Criar model `OHLCCandle` em `market_data/models.py`: FK para `Asset`, campos `timeframe (CharField)`, `timestamp (DateTimeField, db_index=True)`, `open/high/low/close (DecimalField)`, `volume (BigIntegerField)`, `created_at`, `updated_at`; `Meta: unique_together = [('asset', 'timestamp', 'timeframe')]`
  - [x] 2.1.3 Criar `market_data/admin.py` registrando `Asset` e `OHLCCandle` com `list_display` e `list_filter` apropriados
  - [x] 2.1.4 Gerar e aplicar migrations: `makemigrations market_data && migrate`

- [x] **2.2 — App `analysis` — Models**
  - [x] 2.2.1 Criar `analysis/models.py` com model `TechnicalIndicator`: FK para `Asset`, campos `indicator_name (CharField)`, `timeframe (CharField)`, `timestamp (DateTimeField)`, `values (JSONField)`, `created_at`, `updated_at`
  - [x] 2.2.2 Criar model `CandlestickPattern` em `analysis/models.py`: FK para `Asset`, campos `pattern_name (CharField)`, `timeframe (CharField)`, `timestamp (DateTimeField)`, `direction (CharField, choices: BULLISH/BEARISH/NEUTRAL)`, `confidence (DecimalField)`, `created_at`, `updated_at`
  - [x] 2.2.3 Gerar e aplicar migrations: `makemigrations analysis && migrate`

- [x] **2.3 — App `fundamentals` — Models**
  - [x] 2.3.1 Criar `fundamentals/models.py` com model `FundamentalData`: FK para `Asset`, campos `reference_date (DateField)`, `pl_ratio (DecimalField, null=True)`, `roe (DecimalField, null=True)`, `dividend_yield (DecimalField, null=True)`, `ev_ebitda (DecimalField, null=True)`, `raw_data (JSONField, default=dict)`, `created_at`, `updated_at`
  - [x] 2.3.2 Gerar e aplicar migrations

- [x] **2.4 — App `news` — Models**
  - [x] 2.4.1 Criar `news/models.py` com model `NewsArticle`: FK para `Asset (null=True)`, campos `title (CharField)`, `body (TextField)`, `source_url (URLField)`, `source_name (CharField)`, `sentiment (CharField, choices: BULLISH/BEARISH/NEUTRAL)`, `sentiment_score (DecimalField, null=True)`, `published_at (DateTimeField)`, `created_at`, `updated_at`
  - [x] 2.4.2 Gerar e aplicar migrations

- [x] **2.5 — App `ai_agents` — Models**
  - [x] 2.5.1 Criar `ai_agents/models.py` com model `AISignal`: FK para `Asset`, campos `signal_type (CharField, choices: BULLISH/BEARISH/NEUTRAL)`, `confidence_pct (DecimalField)`, `technical_justification (TextField)`, `fundamental_justification (TextField, blank=True)`, `macro_justification (TextField)`, `synthesis_text (TextField)`, `timeframe (CharField)`, `generated_at (DateTimeField)`, `created_at`, `updated_at`
  - [x] 2.5.2 Gerar e aplicar migrations

- [x] **2.6 — App `backtest` — Models**
  - [x] 2.6.1 Criar `backtest/models.py` com model `BacktestResult`: FK para `user (AUTH_USER)`, FK para `asset`, campos `strategy_name (CharField)`, `start_date (DateField)`, `end_date (DateField)`, `initial_capital (DecimalField)`, `final_capital (DecimalField)`, `win_rate (DecimalField)`, `sharpe_ratio (DecimalField)`, `max_drawdown (DecimalField)`, `trades_log (JSONField, default=list)`, `created_at`, `updated_at`
  - [x] 2.6.2 Gerar e aplicar migrations

- [x] **2.7 — App `watchlist` — Models**
  - [x] 2.7.1 Criar `watchlist/models.py` com model `Watchlist`: FK para `user`, FK para `asset`, campo `display_order (IntegerField, default=0)`, `created_at`, `updated_at`; `Meta: unique_together = [('user', 'asset')]`
  - [x] 2.7.2 Criar model `PriceAlert`: FK para `user`, FK para `asset`, campos `condition (CharField, choices: ABOVE/BELOW)`, `target_price (DecimalField)`, `is_active (BooleanField, default=True)`, `is_triggered (BooleanField, default=False)`, `triggered_at (DateTimeField, null=True)`, `created_at`, `updated_at`
  - [x] 2.7.3 Gerar e aplicar migrations

- [x] **2.8 — App `risk` — Models**
  - [x] 2.8.1 Criar `risk/models.py` com model `RiskCalculation`: FK para `user`, FK para `asset`, campos `atr_value (DecimalField)`, `suggested_stop_loss (DecimalField)`, `user_capital (DecimalField)`, `position_size (DecimalField)`, `kelly_fraction (DecimalField)`, `created_at`, `updated_at`
  - [x] 2.8.2 Criar model `MacroIndicator` em `news/models.py` (ou app próprio): campos `name (CharField)`, `source (CharField)`, `reference_date (DateField)`, `value (DecimalField)`, `unit (CharField)`, `created_at`, `updated_at`
  - [x] 2.8.3 Gerar e aplicar migrations

---

### 🏃 Sprint 3 — Dashboard Principal (UI Shell)

- [x] **3.1 — App `dashboard` — Views e URLs**
  - [x] 3.1.1 Criar `dashboard/views.py` com CBV `DashboardView(LoginRequiredMixin, TemplateView)`: `template_name = 'dashboard/index.html'`; context com watchlist do usuário logado
  - [x] 3.1.2 Criar `dashboard/urls.py` com `path('', DashboardView.as_view(), name='dashboard')`
  - [x] 3.1.3 Incluir `path('dashboard/', include('dashboard.urls'))` no `urls.py` raiz

- [x] **3.2 — Template do Dashboard**
  - [x] 3.2.1 Criar `templates/dashboard/index.html` extendendo `base.html`
  - [x] 3.2.2 Implementar header do dashboard: logo, campo de busca de ticker (HTMX `hx-get` para `/market_data/search/`), links "Watchlist", "Alertas", avatar do usuário com dropdown
  - [x] 3.2.3 Implementar grid principal: `grid grid-cols-1 lg:grid-cols-12 gap-4`
  - [x] 3.2.4 Implementar painel do gráfico (`lg:col-span-8`): container para TradingView Lightweight Charts com `id="chart-container"`, seletor de timeframe (1m, 5m, 15m, 1h, 1D)
  - [x] 3.2.5 Implementar painel lateral (`lg:col-span-4`): card "Sinal IA" com placeholder (spinner animado), card "Dados Fundamentalistas" (condicional via Alpine.js `x-show`), card "Gestão de Risco"
  - [x] 3.2.6 Implementar rodapé fixo: ticker de indicadores macro (SELIC, IPCA, USD/BRL) e feed de notícias horizontalmente rolável
  - [x] 3.2.7 Criar `templates/dashboard/partials/signal_card.html` — partial HTMX para o card de sinal IA
  - [x] 3.2.8 Criar `templates/dashboard/partials/fundamental_card.html` — partial para dados fundamentalistas
  - [x] 3.2.9 Criar `templates/dashboard/partials/risk_card.html` — partial para gestão de risco
  - [x] 3.2.10 Criar `templates/dashboard/partials/watchlist_sidebar.html` — partial para sidebar de watchlist

- [x] **3.3 — Integração do TradingView Lightweight Charts**
  - [x] 3.3.1 Adicionar script CDN do TradingView Lightweight Charts 4.x no `base.html` (bloco `extra_js`)
  - [x] 3.3.2 Criar `static/js/chart.js` com inicialização do `createChart()`, série de candlestick, configurações de cores (dark mode: fundo `#0F1629`, grid `#1F2937`, texto `#9CA3AF`)
  - [x] 3.3.3 Implementar função `loadChartData(ticker, timeframe)` em `chart.js` que faz fetch AJAX para `/market-data/ohlc-data/?ticker=X&timeframe=Y` e popula o gráfico
  - [x] 3.3.4 Conectar o campo de busca do header para chamar `loadChartData()` ao confirmar ticker

- [x] **3.4 — Endpoint de Dados para o Gráfico**
  - [x] 3.4.1 Criar CBV `OHLCDataView(LoginRequiredMixin, View)` em `market_data/views.py` que recebe `ticker` e `timeframe` via GET, consulta `OHLCCandle` e retorna `JsonResponse` no formato `[{time, open, high, low, close}, ...]`
  - [x] 3.4.2 Criar `market_data/urls.py` e registrar `path('ohlc-data/', OHLCDataView.as_view(), name='ohlc_data')`
  - [x] 3.4.3 Incluir `path('market-data/', include('market_data.urls'))` no `urls.py` raiz
  - [x] 3.4.4 Criar CBV `AssetSearchView(LoginRequiredMixin, View)` em `market_data/views.py` para busca HTMX de ticker, retorna partial HTML com sugestões

---

### 🏃 Sprint 4 — Coleta de Dados (Celery Tasks)

- [x] **4.1 — Configuração do Celery**
  - [x] 4.1.1 Criar `core/celery.py` com configuração padrão do Celery Django
  - [x] 4.1.2 Atualizar `core/__init__.py` para importar `app` do Celery
  - [x] 4.1.3 Configurar `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TIMEZONE` no `settings.py`
  - [x] 4.1.4 Configurar `CELERY_BEAT_SCHEDULE` no `settings.py` com os 5 schedules de tasks (1min, 1h, 2h, 24h, 24h)

- [x] **4.2 — Tasks de Coleta de OHLC**
  - [x] 4.2.1 Criar `market_data/tasks.py` com task `fetch_intraday_ohlc`: integração Brapi.dev via `httpx`, mapeamento para model `OHLCCandle`, upsert com `update_or_create`, disparo de `run_technical_analysis.delay(asset_id)` ao término
  - [x] 4.2.2 Criar task `fetch_daily_ohlc` em `market_data/tasks.py`: integração `yfinance`, mesma lógica de upsert, disparo de análise
  - [x] 4.2.3 Criar lógica de rollover de contratos em `market_data/utils.py` (função `get_active_contract(asset_type)`) para WIN e WDO

- [x] **4.3 — Tasks de Fundamentais**
  - [x] 4.3.1 Criar `fundamentals/tasks.py` com task `fetch_fundamentals`: scraping do Fundamentus via `httpx` + `BeautifulSoup4`, parsing de P/L, ROE, DY, EV/EBITDA, upsert no model `FundamentalData`
  - [x] 4.3.2 Adicionar retry logic com `autoretry_for=(Exception,)`, `max_retries=3`, `default_retry_delay=60`

- [x] **4.4 — Tasks de Notícias**
  - [x] 4.4.1 Criar `news/tasks.py` com task `fetch_news`: tentativa de scraping Investing.com via `httpx` + User-Agent rotation; fallback para NewsAPI via `httpx`; persistir artigos em `NewsArticle`
  - [x] 4.4.2 Criar `news/utils.py` com função `classify_sentiment(text)` que envia o título da notícia ao LLM e retorna `BULLISH/BEARISH/NEUTRAL`

- [x] **4.5 — Tasks de Dados Macro**
  - [x] 4.5.1 Criar `news/tasks.py` (ou `core/tasks.py`) com task `fetch_macro_data`: integração com API BCB (`api.bcb.gov.br/dados/serie`) para SELIC (série 432), IPCA (série 433), via `httpx`; upsert em `MacroIndicator`

- [x] **4.6 — Signals de Pós-Inserção**
  - [x] 4.6.1 Criar `market_data/signals.py` com signal `post_save` em `OHLCCandle` que dispara `analysis.tasks.run_technical_analysis.delay(instance.asset_id)` quando `created=True`
  - [x] 4.6.2 Criar `market_data/apps.py` e registrar o signal no `ready()` do `AppConfig`

---

### 🏃 Sprint 5 — Motor de Análise Técnica

- [x] **5.1 — Cálculo de Indicadores**
  - [x] 5.1.1 Criar `analysis/tasks.py` com task `run_technical_analysis(asset_id)`: busca os últimos N candles do asset, calcula RSI (período 14), MACD (12,26,9), Bollinger Bands (período 20, desvio 2) usando `pandas-ta`, persiste resultado em `TechnicalIndicator`
  - [x] 5.1.2 Implementar cálculo de ATR (período 14) em `analysis/utils.py` (função `calculate_atr(df)`) — resultado usado também pelo módulo de risco
  - [x] 5.1.3 Criar `analysis/tasks.py` — subtask `detect_candlestick_patterns(asset_id)`: usar TA-Lib para detectar padrões (`talib.CDLENGULFING`, `talib.CDLHAMMER`, etc.), persistir em `CandlestickPattern`

- [x] **5.2 — Cálculo de Fibonacci**
  - [x] 5.2.1 Criar função `calculate_fibonacci_levels(high, low)` em `analysis/utils.py`: retorna dict com níveis 0%, 23.6%, 38.2%, 50%, 61.8%, 78.6%, 100%
  - [x] 5.2.2 Integrar os níveis como overlay no gráfico TradingView via `static/js/chart.js` (série de linhas horizontais)

- [x] **5.3 — Endpoint de Indicadores para o Frontend**
  - [x] 5.3.1 Criar CBV `IndicatorDataView(LoginRequiredMixin, View)` em `analysis/views.py`: retorna `JsonResponse` com últimos valores de RSI, MACD, Bollinger para o ticker/timeframe solicitado
  - [x] 5.3.2 Criar `analysis/urls.py` e registrar `path('indicators/', IndicatorDataView.as_view(), name='indicators')`
  - [x] 5.3.3 Integrar overlay de Bollinger Bands no gráfico TradingView (série de bandas)
  - [x] 5.3.4 Criar sub-gráficos de RSI e MACD abaixo do candlestick principal via TradingView Lightweight Charts

---

### 🏃 Sprint 6 — Sistema Multi-Agente IA (LangGraph)

- [x] **6.1 — Configuração LangGraph**
  - [x] 6.1.1 Instalar `langgraph`, `langchain`, `langchain-google-genai` (ou `langchain-openai`) no `requirements.txt`
  - [x] 6.1.2 Criar `ai_agents/graph.py` com definição do `StateGraph` usando `TypedDict` para o estado compartilhado
  - [x] 6.1.3 Definir `AgentState` com campos: `ticker`, `asset_type`, `technical_analysis`, `fundamental_analysis`, `macro_analysis`, `signal`, `confidence`, `synthesis`

- [x] **6.2 — Technical Agent**
  - [x] 6.2.1 Criar `ai_agents/agents/technical_agent.py` com função `technical_node(state)`: busca `TechnicalIndicator`, `CandlestickPattern` e níveis Fibonacci do banco; formata contexto; chama LLM para gerar análise textual; retorna estado atualizado com `technical_analysis`

- [x] **6.3 — Fundamental Agent**
  - [x] 6.3.1 Criar `ai_agents/agents/fundamental_agent.py` com função `fundamental_node(state)`: executado apenas se `asset_type == 'STOCK'`; busca `FundamentalData` do banco; chama LLM para gerar análise; retorna estado atualizado com `fundamental_analysis`

- [x] **6.4 — Macro/News Agent**
  - [x] 6.4.1 Criar `ai_agents/agents/macro_agent.py` com função `macro_node(state)`: busca `MacroIndicator` (SELIC, IPCA, PIB) e últimos `NewsArticle` com sentiment do ticker; chama LLM; retorna estado atualizado com `macro_analysis`

- [x] **6.5 — Supervisor e Synthesis**
  - [x] 6.5.1 Criar `ai_agents/agents/supervisor.py` com função `route_agents(state)`: decide quais nós acionar com base em `asset_type`
  - [x] 6.5.2 Criar `ai_agents/agents/synthesis.py` com função `synthesis_node(state)`: recebe as 3 análises, chama LLM para consolidar e emitir sinal final `BULLISH/BEARISH/NEUTRAL` com `confidence_pct` e `synthesis_text`; persiste em `AISignal`

- [x] **6.6 — Task Celery para Execução do Grafo**
  - [x] 6.6.1 Criar `ai_agents/tasks.py` com task `run_ai_analysis(asset_id)`: instancia o grafo, executa com estado inicial, persiste resultado em `AISignal`
  - [x] 6.6.2 Criar `ai_agents/signals.py` com signal `post_save` em `TechnicalIndicator` que dispara `run_ai_analysis.delay(instance.asset_id)` quando `created=True`
  - [x] 6.6.3 Registrar signal no `ai_agents/apps.py`

- [x] **6.7 — Cache Redis para Sinais IA**
  - [x] 6.7.1 Configurar `django.core.cache` com backend Redis no `settings.py`
  - [x] 6.7.2 Na task `run_ai_analysis`, verificar cache `ai_signal_{asset_id}` antes de executar o grafo; salvar resultado no cache por 300 segundos após execução

---

### 🏃 Sprint 7 — WebSocket, Chat IA, Backtest e Watchlist

- [x] **7.1 — Django Channels e WebSocket**
  - [x] 7.1.1 Configurar `ASGI_APPLICATION` e `CHANNEL_LAYERS` com Redis no `settings.py`
  - [x] 7.1.2 Criar `trade_intelligence/asgi.py` com roteamento `URLRouter` para WebSocket
  - [x] 7.1.3 Criar `dashboard/consumers.py` com `AsyncWebsocketConsumer` `AssetConsumer`: join/leave grupo do ticker, receber e enviar mensagens de sinal IA
  - [x] 7.1.4 Criar `dashboard/routing.py` com `websocket_urlpatterns` mapeando `ws/asset/<ticker>/`
  - [x] 7.1.5 Na task `run_ai_analysis`, após persistir o sinal, publicar resultado no channel group `asset_{ticker}` via `channels.layers.get_channel_layer().group_send()`
  - [x] 7.1.6 Criar `static/js/websocket.js` com lógica de conexão WebSocket no frontend: ao receber mensagem, atualizar o card de sinal IA via DOM manipulation

- [x] **7.2 — Chat IA**
  - [x] 7.2.1 Criar `templates/dashboard/partials/chat_panel.html` com área de histórico de mensagens e input de texto
  - [x] 7.2.2 Criar CBV `ChatView(LoginRequiredMixin, View)` em `ai_agents/views.py`: recebe `ticker` e `message` via POST, monta contexto com dados do banco, chama LLM, retorna resposta via `JsonResponse`
  - [x] 7.2.3 Criar `ai_agents/urls.py` e registrar `path('chat/', ChatView.as_view(), name='chat')`
  - [x] 7.2.4 Integrar HTMX no chat: `hx-post` no formulário, `hx-swap="beforeend"` na área de histórico

- [x] **7.3 — Backtest**
  - [x] 7.3.1 Criar `backtest/forms.py` com `BacktestForm(forms.Form)`: campos `ticker (CharField)`, `start_date (DateField)`, `end_date (DateField)`, `strategy (ChoiceField)`, `initial_capital (DecimalField)`; validação `clean()` verificando `start_date < end_date`
  - [x] 7.3.2 Criar CBV `BacktestView(LoginRequiredMixin, FormView)` em `backtest/views.py`: `form_class = BacktestForm`, `template_name = 'backtest/form.html'`; no `form_valid()`, chamar task `run_backtest.delay()`
  - [x] 7.3.3 Criar `backtest/tasks.py` com task `run_backtest(user_id, ticker, start_date, end_date, strategy, capital)`: busca OHLC do banco, executa `backtesting.py`, persiste resultado em `BacktestResult`
  - [x] 7.3.4 Criar CBV `BacktestResultView(LoginRequiredMixin, DetailView)` em `backtest/views.py`: exibe resultado com Win Rate, Sharpe, Drawdown
  - [x] 7.3.5 Criar `templates/backtest/form.html` e `templates/backtest/result.html` com design dark mode
  - [x] 7.3.6 Criar `backtest/urls.py` e registrar URLs

- [x] **7.4 — Watchlist e Alertas**
  - [x] 7.4.1 Criar `watchlist/forms.py` com `PriceAlertForm(forms.ModelForm)`: campos `condition`, `target_price`; `Meta: model = PriceAlert, fields = [...]`
  - [x] 7.4.2 Criar CBV `WatchlistAddView(LoginRequiredMixin, View)` em `watchlist/views.py`: POST com `ticker`, cria `Watchlist` entry, retorna partial HTML atualizado (HTMX)
  - [x] 7.4.3 Criar CBV `WatchlistRemoveView(LoginRequiredMixin, View)` em `watchlist/views.py`: POST com `asset_id`, remove entry, retorna partial HTML
  - [x] 7.4.4 Criar CBV `AlertCreateView(LoginRequiredMixin, CreateView)` em `watchlist/views.py`: usa `PriceAlertForm`
  - [x] 7.4.5 Criar task `check_price_alerts` em `watchlist/tasks.py`: agendada a cada 1 minuto, verifica `PriceAlert.objects.filter(is_active=True)`, compara com último preço, publica notificação via Channels se condição satisfeita
  - [x] 7.4.6 Criar `watchlist/signals.py` com signal `post_save` em `PriceAlert` para log de auditoria
  - [x] 7.4.7 Criar `watchlist/urls.py` e registrar todas as URLs
  - [x] 7.4.8 Criar `templates/watchlist/` com templates `alert_list.html`, `alert_form.html`

- [x] **7.5 — Gestão de Risco**
  - [x] 7.5.1 Criar `risk/forms.py` com `RiskForm(forms.Form)`: campo `user_capital (DecimalField)`
  - [x] 7.5.2 Criar CBV `RiskCalculationView(LoginRequiredMixin, FormView)` em `risk/views.py`: no `form_valid()`, busca ATR do asset via `analysis/utils.py`, calcula position sizing (Kelly simplificado: `f = (win_rate * avg_win - loss_rate * avg_loss) / avg_win`), persiste em `RiskCalculation`, retorna partial HTML (HTMX)
  - [x] 7.5.3 Criar `risk/urls.py` e registrar URL
  - [x] 7.5.4 Atualizar `templates/dashboard/partials/risk_card.html` com formulário HTMX e área de resultado

---

### 🏃 Sprint 8 — Docker e Infraestrutura de Produção

- [ ] **8.1 — Dockerfile**
  - [ ] 8.1.1 Criar `Dockerfile` multi-stage: stage `builder` (instala TA-Lib, dependências Python); stage `runtime` (copia artefatos, configura usuário não-root, CMD `gunicorn`)
  - [ ] 8.1.2 Criar `.dockerignore` excluindo `db.sqlite3`, `.env`, `__pycache__`, `node_modules`

- [ ] **8.2 — Docker Compose**
  - [ ] 8.2.1 Criar `docker-compose.yml` com serviços: `web` (Django/Gunicorn), `celery-worker`, `celery-beat`, `redis`, `postgres` (com TimescaleDB), `nginx`
  - [ ] 8.2.2 Configurar volumes persistentes para `postgres_data` e `static_files`
  - [ ] 8.2.3 Configurar variáveis de ambiente via `env_file: .env` em todos os serviços

- [ ] **8.3 — Nginx**
  - [ ] 8.3.1 Criar `nginx/nginx.conf` com: proxy reverso para Gunicorn na porta 8000, proxy WebSocket para Channels (Daphne) na porta 8001, serve arquivos estáticos diretamente, configuração SSL placeholder

- [ ] **8.4 — Migração para PostgreSQL + TimescaleDB**
  - [ ] 8.4.1 Atualizar `DATABASE_URL` no `.env` para apontar para PostgreSQL
  - [ ] 8.4.2 Instalar `psycopg2-binary` e `django-timescaledb` no `requirements.txt`
  - [ ] 8.4.3 Configurar `OHLCCandle` como hypertable: adicionar `timescale = TimescaleModel()` e `time_column_name = 'timestamp'`
  - [ ] 8.4.4 Executar migrations no container e verificar criação das hypertables

- [ ] **8.5 — Build TailwindCSS para Produção**
  - [ ] 8.5.1 Configurar `tailwind.config.js` com `content` apontando para todos os templates Django
  - [ ] 8.5.2 Criar script `build_css.sh` para gerar CSS minificado: `npx tailwindcss -i ./static/css/main.css -o ./static/css/output.css --minify`
  - [ ] 8.5.3 Atualizar `base.html` para usar `output.css` em produção (condicional `{% if not DEBUG %}`)

---

### 🏃 Sprint 9 — Testes Automatizados

- [ ] **9.1 — Configuração de Testes**
  - [ ] 9.1.1 Instalar `pytest-django`, `factory-boy`, `pytest-celery` no `requirements-dev.txt`
  - [ ] 9.1.2 Criar `pytest.ini` com `DJANGO_SETTINGS_MODULE = 'trade_intelligence.settings'`
  - [ ] 9.1.3 Criar `conftest.py` na raiz com fixtures: `db`, `authenticated_client`, `sample_asset`, `sample_ohlc_candles`

- [ ] **9.2 — Testes de Models**
  - [ ] 9.2.1 Criar `market_data/tests/test_models.py`: testar criação de `Asset` e `OHLCCandle`, unicidade de `(asset, timestamp, timeframe)`, presença de `created_at` e `updated_at`
  - [ ] 9.2.2 Criar `watchlist/tests/test_models.py`: testar criação de `Watchlist` e `PriceAlert`, unicidade de `(user, asset)` na watchlist
  - [ ] 9.2.3 Criar `ai_agents/tests/test_models.py`: testar criação de `AISignal` com choices válidos

- [ ] **9.3 — Testes de Views (CBVs)**
  - [ ] 9.3.1 Criar `dashboard/tests/test_views.py`: testar redirect de unauthenticated user para login; testar retorno 200 de `DashboardView` para user autenticado
  - [ ] 9.3.2 Criar `market_data/tests/test_views.py`: testar `OHLCDataView` retorna JSON válido; testar `AssetSearchView` retorna sugestões
  - [ ] 9.3.3 Criar `backtest/tests/test_views.py`: testar `BacktestView` com form inválido (data início > data fim) retorna erro; testar form válido dispara task

- [ ] **9.4 — Testes de Forms**
  - [ ] 9.4.1 Criar `backtest/tests/test_forms.py`: testar validação `start_date < end_date`
  - [ ] 9.4.2 Criar `watchlist/tests/test_forms.py`: testar `PriceAlertForm` com `target_price` negativo

- [ ] **9.5 — Testes de Tasks Celery**
  - [ ] 9.5.1 Criar `market_data/tests/test_tasks.py`: testar `fetch_daily_ohlc` com mock do `yfinance`, verificar criação de `OHLCCandle`
  - [ ] 9.5.2 Criar `analysis/tests/test_tasks.py`: testar `run_technical_analysis` com OHLC mockado, verificar criação de `TechnicalIndicator`
  - [ ] 9.5.3 Criar `watchlist/tests/test_tasks.py`: testar `check_price_alerts` dispara notificação quando condição é satisfeita

- [ ] **9.6 — Testes de Análise Técnica**
  - [ ] 9.6.1 Criar `analysis/tests/test_utils.py`: testar `calculate_atr()` com DataFrame de OHLC fixo e verificar resultado esperado; testar `calculate_fibonacci_levels(high, low)` com valores conhecidos

---