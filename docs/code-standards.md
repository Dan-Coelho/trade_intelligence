# Padrões de Código — Trade Intelligence B3

Regras obrigatórias para todo código adicionado ao projeto. Nenhuma exceção sem documentação explícita.

---

## Linguagem e Formatação

- **Todo código Python em inglês**: nomes de classes, variáveis, funções, arquivos e diretórios.
- **PEP 8** estrito. Use um linter (ex: `ruff`) para garantir conformidade.
- **Aspas simples** em todo código Python. Exceto quando a string contém aspas simples internas — use aspas duplas nesses casos.

```python
# ✅ correto
ticker = 'PETR4'
message = "It's a bullish signal"

# ❌ errado
ticker = "PETR4"
```

- Interface do usuário (labels, mensagens, textos de templates) 100% em **Português Brasileiro (PT-BR)**.

---

## Views

- Usar exclusivamente **Class-Based Views (CBVs)** do Django.
- Function-based views são proibidas, salvo em casos excepcionais com justificativa documentada em comentário no código.
- Todas as views que exigem autenticação devem usar `LoginRequiredMixin` como primeiro mixin.

```python
# ✅ correto
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/index.html'
```

---

## Formulários

- Todo formulário deve ser uma classe que herda de `forms.Form` ou `forms.ModelForm`.
- Nunca manipular dados de requisição diretamente na view sem passar por uma classe de formulário.

```python
# ✅ correto
from django import forms

class BacktestForm(forms.Form):
    ticker = forms.CharField(max_length=10)
    start_date = forms.DateField()
    end_date = forms.DateField()
    initial_capital = forms.DecimalField(min_value=0)

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and start >= end:
            raise forms.ValidationError('Data de início deve ser anterior à data de fim.')
        return cleaned_data
```

---

## Models

- Todos os models Django **devem** conter os campos de auditoria:

```python
created_at = models.DateTimeField(auto_now_add=True)
updated_at = models.DateTimeField(auto_now=True)
```

- Exemplo de model compliant:

```python
from django.db import models

class Asset(models.Model):
    STOCK = 'STOCK'
    FUTURE = 'FUTURE'
    ASSET_TYPE_CHOICES = [
        (STOCK, 'Ação'),
        (FUTURE, 'Contrato Futuro'),
    ]

    ticker = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPE_CHOICES)
    exchange = models.CharField(max_length=10, default='B3')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.ticker
```

---

## Signals

- Todos os signals Django devem estar em um arquivo chamado **`signals.py`** dentro do respectivo app.
- Nunca definir signals em `models.py` ou `apps.py` diretamente.
- O signal deve ser conectado no método `ready()` do `AppConfig` do app.

```python
# analysis/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TechnicalIndicator

@receiver(post_save, sender=TechnicalIndicator)
def trigger_ai_analysis(sender, instance, created, **kwargs):
    if created:
        from ai_agents.tasks import run_ai_analysis
        run_ai_analysis.delay(instance.asset_id)
```

```python
# analysis/apps.py
from django.apps import AppConfig

class AnalysisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analysis'

    def ready(self):
        import analysis.signals  # noqa: F401
```

---

## Celery Tasks

- Tasks Celery ficam em **`tasks.py`** dentro do respectivo app.
- Tasks que fazem requisições externas devem ter retry configurado:

```python
@app.task(
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
)
def fetch_daily_ohlc():
    ...
```

---

## Estrutura de URLs

- Cada app deve ter seu próprio `urls.py`.
- O `core/urls.py` apenas inclui as rotas de cada app via `include()`.

```python
# core/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core_app.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('accounts/', include('allauth.urls')),
    path('market-data/', include('market_data.urls')),
]
```

---

## Configuração de Ambiente

- Secrets e API keys **nunca** no código-fonte. Sempre via variáveis de ambiente lidas pelo `python-decouple`.
- O arquivo `.env` está no `.gitignore` e nunca deve ser versionado.

```python
# settings.py (padrão após Sprint 0 completa)
from decouple import config

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', cast=bool, default=False)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='').split(',')
```

---

## Resumo das Regras (checklist rápido)

| Regra | Obrigatório |
|---|---|
| Código Python em inglês | ✅ |
| PEP 8 | ✅ |
| Aspas simples no Python | ✅ |
| CBVs (sem FBVs) | ✅ |
| `LoginRequiredMixin` em views protegidas | ✅ |
| `forms.Form` ou `forms.ModelForm` | ✅ |
| `created_at` e `updated_at` em todos os models | ✅ |
| Signals em `signals.py` do respectivo app | ✅ |
| Signals registrados no `ready()` do AppConfig | ✅ |
| Tasks Celery em `tasks.py` do respectivo app | ✅ |
| Secrets via `.env` + `python-decouple` | ✅ |
| UI em Português Brasileiro | ✅ |
