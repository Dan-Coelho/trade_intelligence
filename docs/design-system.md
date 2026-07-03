# Design System — Trade Intelligence B3

Interface 100% em **dark mode nativo**, com paleta azul/ciano, tipografia Inter e TailwindCSS 3.x.

> As classes listadas aqui são o padrão para todos os templates do projeto. Nunca use estilos inline ou classes ad-hoc que contrariem este documento.

---

## Paleta de Cores

| Token | Descrição | Hex | Classe TailwindCSS |
|---|---|---|---|
| `--color-bg-primary` | Fundo principal da página | `#0A0E1A` | `bg-[#0A0E1A]` |
| `--color-bg-surface` | Cards e painéis | `#111827` | `bg-gray-900` |
| `--color-bg-elevated` | Hover, modais, dropdowns | `#1F2937` | `bg-gray-800` |
| `--color-border` | Bordas sutis | `#374151` | `border-gray-700` |
| `--color-primary` | Ação primária (botão principal) | `#3B82F6` | `bg-blue-500` |
| `--color-primary-hover` | Hover do botão primário | `#2563EB` | `hover:bg-blue-600` |
| `--color-accent` | Destaque, gradiente de logo | `#06B6D4` | `text-cyan-400` |
| `--color-bullish` | Sinal Bullish (alta) | `#10B981` | `text-emerald-400` |
| `--color-bearish` | Sinal Bearish (baixa) | `#EF4444` | `text-red-400` |
| `--color-neutral` | Sinal Neutro | `#9CA3AF` | `text-gray-400` |
| `--color-text-primary` | Texto principal | `#F9FAFB` | `text-gray-50` |
| `--color-text-secondary` | Texto secundário | `#9CA3AF` | `text-gray-400` |
| `--color-text-muted` | Texto desabilitado / placeholder | `#6B7280` | `text-gray-500` |

### Gradientes

| Token | Uso | Classes TailwindCSS |
|---|---|---|
| `--gradient-header` | Background do header | `bg-gradient-to-r from-[#1E3A5F] to-[#0A0E1A]` |
| `--gradient-signal-bullish` | Card de sinal Bullish | `bg-gradient-to-br from-emerald-900/40 to-emerald-800/20` |
| `--gradient-signal-bearish` | Card de sinal Bearish | `bg-gradient-to-br from-red-900/40 to-red-800/20` |
| `--gradient-logo` | Texto do logo | `bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent` |

---

## Tipografia

Fonte base: **Inter** — importada via Google Fonts no `<head>` do `base.html`.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

| Elemento | Peso / Tamanho | Classe TailwindCSS |
|---|---|---|
| Título de página `<h1>` | Inter 700 / 2rem | `text-3xl font-bold tracking-tight text-gray-50` |
| Título de seção `<h2>` | Inter 600 / 1.5rem | `text-2xl font-semibold text-gray-50` |
| Título de card `<h3>` | Inter 600 / 1.125rem | `text-lg font-semibold text-gray-50` |
| Texto de corpo | Inter 400 / 0.875rem | `text-sm text-gray-400` |
| Label de campo | Inter 500 / 0.75rem | `text-xs font-medium text-gray-400 uppercase tracking-wide` |
| Dado numérico / ticker | Inter Mono 600 | `font-mono font-semibold tabular-nums` |

---

## Botões

| Variante | Quando usar | Classes TailwindCSS |
|---|---|---|
| **Primary** | Ação principal (Analisar, Cadastrar, Entrar) | `bg-blue-500 hover:bg-blue-600 text-white font-semibold px-4 py-2 rounded-lg transition-colors duration-200` |
| **Secondary** | Ação secundária (Cancelar, Voltar) | `bg-gray-700 hover:bg-gray-600 text-gray-100 font-medium px-4 py-2 rounded-lg transition-colors duration-200` |
| **Danger** | Ações destrutivas (Remover, Excluir) | `bg-red-700 hover:bg-red-600 text-white font-medium px-4 py-2 rounded-lg transition-colors duration-200` |
| **Ghost** | Links de navegação, ações terciárias | `text-gray-400 hover:text-white hover:bg-gray-800 px-3 py-2 rounded-md transition-all duration-200` |
| **Icon** | Botões com apenas ícone | `p-2 rounded-full bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors duration-200` |

---

## Inputs e Formulários

### Input de texto

```html
<input
  type="text"
  class="bg-gray-800 border border-gray-700 text-gray-100 placeholder-gray-500
         rounded-lg px-3 py-2 text-sm w-full
         focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
         transition-all duration-200"
>
```

### Select

```html
<select class="bg-gray-800 border border-gray-700 text-gray-100 rounded-lg px-3 py-2 text-sm w-full focus:ring-2 focus:ring-blue-500">
```

### Label

```html
<label class="block text-xs font-medium text-gray-400 mb-1 uppercase tracking-wide">
  Ticker
</label>
```

### Erro inline

```html
<p class="text-red-400 text-xs mt-1">Este campo é obrigatório.</p>
```

### Container de formulário

```html
<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 shadow-xl">
  <!-- campos aqui -->
</div>
```

---

## Cards

### Card base

```html
<div class="bg-gray-900 border border-gray-700/50 rounded-xl p-5 shadow-lg">
```

### Card de Sinal Bullish

```html
<div class="bg-gradient-to-br from-emerald-900/40 to-emerald-800/20 border border-emerald-700/50 rounded-xl p-5">
```

### Card de Sinal Bearish

```html
<div class="bg-gradient-to-br from-red-900/40 to-red-800/20 border border-red-700/50 rounded-xl p-5">
```

### Card de Sinal Neutro

```html
<div class="bg-gradient-to-br from-gray-800/40 to-gray-700/20 border border-gray-600/50 rounded-xl p-5">
```

---

## Layout do Dashboard

### Wrapper da página

```html
<div class="min-h-screen bg-[#0A0E1A] flex flex-col text-gray-50 font-sans">
```

### Header

```html
<header class="w-full bg-gradient-to-r from-[#1E3A5F] to-[#0A0E1A] border-b border-gray-700/50">
  <nav class="flex items-center justify-between h-16 px-6">
```

### Grid principal

```html
<main class="grid grid-cols-1 lg:grid-cols-12 gap-4 p-4 flex-1">
  <section class="lg:col-span-8">  <!-- Gráfico -->
  <aside class="lg:col-span-4">   <!-- Painel lateral -->
```

### Footer

```html
<footer class="w-full bg-gray-900 border-t border-gray-700/50 px-4 py-2">
```

### Responsividade

| Breakpoint | Comportamento |
|---|---|
| Mobile `< 768px` | Coluna única. Gráfico no topo, painel IA abaixo |
| Tablet `768px – 1280px` | Grid 2 colunas (8/4) |
| Desktop `> 1280px` | Grid 12 colunas — `col-span-8` para gráfico, `col-span-4` para painel lateral |

---

## Header — Detalhes de Componentes

```html
<!-- Logo -->
<span class="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
  Trade Intelligence
</span>

<!-- Campo de busca -->
<input
  type="search"
  placeholder="Buscar ticker..."
  class="bg-gray-800/80 backdrop-blur-sm border border-gray-700 rounded-full
         px-4 py-1.5 text-sm w-64 focus:ring-1 focus:ring-blue-500 focus:outline-none"
>

<!-- Avatar do usuário -->
<div class="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500
            flex items-center justify-center text-white text-sm font-bold">
  {{ user.username|first|upper }}
</div>
```
