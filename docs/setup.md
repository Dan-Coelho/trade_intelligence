# Setup — Ambiente de Desenvolvimento

---

## Pré-requisitos

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (gerenciador de pacotes e virtualenv)
- Redis rodando localmente (para Celery)

---

## Instalação

### 1. Clonar o repositório

```bash
git clone <url-do-repositorio>
cd trade_indicator
```

### 2. Criar e ativar o ambiente virtual

```bash
uv venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate
```

### 3. Instalar dependências

```bash
uv sync
```

As dependências estão definidas em `pyproject.toml`:

```toml
dependencies = [
    "celery>=5.6.3",
    "channels>=4.3.2",
    "django>=5.2.15",
    "django-allauth>=65.18.0",
    "htmx>=0.0.0",
    "redis>=8.0.1",
]
```

### 4. Configurar variáveis de ambiente

Copie o arquivo `.env` de exemplo e preencha os valores:

```
SECRET_KEY=<sua-secret-key>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
LLM_PROVIDER=gemini
LLM_API_KEY=<sua-api-key>
REDIS_URL=redis://localhost:6379/0
```

> **Atenção:** o `settings.py` atual ainda carrega configurações hardcoded. A integração com `python-decouple` para leitura do `.env` está pendente (tarefa 0.1.5).

### 5. Aplicar migrations

```bash
python manage.py migrate
```

### 6. Rodar o servidor de desenvolvimento

```bash
python manage.py runserver
```

O servidor sobe em `http://127.0.0.1:8000/`.

---

## Estrutura do settings.py (atual)

| Configuração | Valor atual |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `core.settings` |
| `DEBUG` | `True` (hardcoded) |
| `DATABASE` | SQLite (`db.sqlite3` na raiz) |
| `LANGUAGE_CODE` | `en-us` (pendente: mudar para `pt-br`) |
| `TIME_ZONE` | `UTC` (pendente: mudar para `America/Sao_Paulo`) |
| `STATIC_URL` | `static/` |
| `DEFAULT_AUTO_FIELD` | `BigAutoField` |

---

## Arquivos ignorados pelo git

Configurados no `.gitignore`:

```
__pycache__/
*.py[oc]
build/
dist/
wheels/
*.egg-info
.env
.venv
node_modules/
db.sqlite3
```
