# Documentação — Trade Intelligence B3

Índice da documentação técnica do projeto. Todos os arquivos abaixo cobrem **exclusivamente o que está implementado ou definido** no projeto.

---

## Índice

| Arquivo | O que cobre |
|---|---|
| [architecture.md](./architecture.md) | Visão geral do projeto, estrutura de apps e stack tecnológica |
| [setup.md](./setup.md) | Como configurar e rodar o projeto localmente |
| [code-standards.md](./code-standards.md) | Padrões de código obrigatórios (PEP 8, CBVs, models, signals) |
| [design-system.md](./design-system.md) | Paleta de cores, tipografia, botões, inputs e layout (TailwindCSS) |

---

## Estado Atual do Projeto

O projeto está na **Sprint 0** — scaffold criado. O que existe hoje:

- Projeto Django inicializado (`core/` como pacote de configuração)
- 11 apps Django criados e registrados no `INSTALLED_APPS` (todos ainda com arquivos gerados pelo scaffold, sem implementação)
- Dependências instaladas via `uv` / `pyproject.toml`
- `.env` com as variáveis de ambiente definidas (sem valores preenchidos)
- `.gitignore` configurado

Consulte o [PRD.md](../PRD.md) para o escopo completo planejado e o [TASKS.md](../TASKS.md) para o progresso das sprints.
