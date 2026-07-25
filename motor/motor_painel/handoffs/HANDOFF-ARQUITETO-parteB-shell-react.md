# HANDOFF ARQUITETO → Operário — Parte B: App Shell React

> **Para o Operário (Construtor).** Execute UM handoff = UM commit.
> Ao terminar: mostre diff + resultado dos testes + avise o Arquiteto.

## Objetivo
Construir o **app shell** React que serve de fundação para as 20 telas do painel. O scaffold Vite já existe em `app/` — você vai **substituir** o conteúdo de placeholder (counter demo) pelo shell real com nav lateral, roteador client-side, sistema de temas e cliente de API.

## Arquivos que você DEVE ler antes de começar
- `motor_painel/telas/README.md` — handoff do designer, sistema visual
- `motor_painel/telas/mf-themes.js` — especificação literal do sistema de temas
- `motor_painel/PLANO-PAINEL.md` — ordem das telas e tiers
- `motor_painel/HANDOFF-01-contrato-e-shell.md` — missão completa (contexto)
- `motor_painel/painel.py` — contrato de dados (endpoints que o shell consome)

## O que construir — checklist exato

### 1. Sistema de temas (arquivo único de tokens)
- **`app/src/theme.css`** — camada ÚNICA de CSS custom properties. ZERO hex literal fora deste arquivo em qualquer outro lugar.
- Tokens do tema escuro "metafabrica" como default (`.mf-root`):
  `--bg #0B0C0E` · `--surface #121417` · `--surface2 #17191D` · `--border #26292E` · `--focus #3E434A` · `--text #E8E6E1` · `--text2 #8A8F98` · `--text3 #5A5F66` · `--accent #E8A33D` · `--red #E5484D` · `--amber #E8A33D` · `--green #30A46C` · `--blue #3E63DD` · `--inv-bg #E8E6E1` · `--inv-text #0B0C0E` · `--grap1 #2A2D33` · `--grap2 #3A3E46` · `--rim #55596200`
- Temas builtins (metafabrica, gemini, framer) — cada um com set escuro + set claro — implementados como `[data-theme="gemini"]`, `[data-theme="framer"]` via CSS. Os valores de cada builtin estão em `mf-themes.js` (array `BUILTINS`). Use-os como especificação literal.
- Claro = `[data-theme="stark"]` (compartilhado pelos 3 — valores exatos no `mf-themes.js`, objeto `LIGHT_AZUL`).
- O `body` deve usar `background: var(--bg)`.
- Não precisa recriar `mf-themes.js` como JS runtime — o tema é CSS puro + um `data-theme` attribute no `body`.
- **Gatilho de troca de tema:** toggle `◐` na topbar comuta `body.dataset.theme` entre `"stark"` e `""` (escuro). Persiste em `localStorage['mf-theme-active']`.

### 2. Tipografia (em `theme.css` ou `index.css`)
Fontes do design (Google Fonts):
- **Space Grotesk** — títulos (`.title`), pesos 400/500/600/700
- **IBM Plex Mono** — dados/labels/IDs/custo (`.mono`, `.eyebrow`, `.num`), pesos 400/500/600
- **Inter** — corpo, peso 400/500/600
Base 14px.

### 3. Layout padrão (componentes React)
Layout fixo, presente em TODA rota:
- **Topbar (`app/src/components/Topbar.jsx`):** 52px altura, `border-bottom: 1px solid var(--border)`, `background: var(--surface)`. Conteúdo: logo (quadrado 19×19 com borda dupla), texto "META-FÁBRICA", toggle tema `◐` (alterna `body.dataset.theme`), botão "+ Nova missão" (`.btn.btn-primary`), sino com badge. Usa `display: flex; align-items: center; gap: 12px; padding: 0 18px`.
- **Sidebar (`app/src/components/Sidebar.jsx`):** 238px largura fixa, `border-right: 1px solid var(--border)`, `background: var(--surface)`. 4 zonas com labels (`.zt` — zona title):
  - **Fixas** (`.zt.fixed`): Home, Runs, CaixaFundador, Grafo2D
  - **Projeto**: NovaMissao, Dashboard, Custos
  - **Biblioteca**: Agentes, Skills, CatalogoWorkflows, Inventario, CuradorAnalise, Board
  - **Sistema**: Configuracoes/Temas, Logs, Datahouse, Runners, MapaGeral
- Cada nav item (`.ni`) = `display: flex; align-items: center; gap: 9px; padding: 7px 18px; font-size: 13px; color: var(--text2); border-left: 2px solid transparent; cursor: pointer`. Ativo (`.ni.on`) = `color: var(--text); background: var(--surface2); border-left-color: var(--accent); font-weight: 600`.
- **Body layout:** `.mf-body` = `display: flex; flex: 1; min-height: 0` — sidebar + main area.
- **Main area:** componente `<Outlet />` do router (ou equivalente — cada rota renderiza aqui).

### 4. Roteador client-side (sem recarregar)
- Use `window.history.pushState` + evento `popstate` (ou uma micro-biblioteca se quiser — mas zero deps novas no `package.json` além do que já está). Nada de React Router se não quiser — roteador manual fino é aceitável.
- Cada rota = um componente React, carregado dinamicamente (lazy ou direto, decide você).
- Rotas por enquanto (Tier 1): `/`, `/runs`, `/caixa`, `/grafo2d`.
- As demais rotas (Tier 2/3) ficam no sidebar como itens visuais mas **sem componente implementado** — link pra `/em-breve` ou simplesmente um `disabled`.
- Troca de rota troca só o conteúdo da main area, nunca recarrega a página.

### 5. Cliente de API (`app/src/api.js`)
Módulo JS puro:
```js
export function fetchJSON(path) { return fetch(path).then(r => r.json()); }
export function startPoll(path, intervalMs, onData) {
  let alive = true;
  function poll() { if (!alive) return; fetchJSON(path).then(onData).finally(() => alive && setTimeout(poll, intervalMs)); }
  poll();
  return () => { alive = false; };
}
```
Nada mais complexo que isso. `fetch('/dados/runs')`, `fetch('/dados/runs/<id>')`, `fetch('/dados/gates')`, etc. Poll 2s onde necessário.

### 6. Tela de prova — Runs (`app/src/routes/Runs.jsx`)
Consome `/dados/runs` via `api.js`:
- Lista de runs: cada linha mostra `id`, `objetivo`, `estado` (com StatusShape: círculo azul = ativa, verde = concluída, vermelho losango = abortada), `inicio`, `custo`, `n_eventos`.
- Ao clicar numa run: busca `/dados/runs/<id>`, mostra painel de detalhe com:
  - Resumo (objetivo, estado, custo, nº eventos)
  - Lista de artefatos (eventos `executor.respondeu` com `artefato`/`artefatos`)
  - Lista de gates (eventos `portao.*` + `escalado` + `decisao.*`)
- Enquanto a run está ativa (estado !== "concluida" e !== "abortada"), faz poll a cada 2s para atualizar o detalhe ao vivo.
- Se nenhuma run existe, mostra "Nenhuma run registrada" (não quebra).

### 7. Home placeholder (`app/src/routes/Home.jsx`)
Só um placeholder: "Home — em construção". Usa layout padrão (topbar + sidebar + main area com texto). Serve para testar troca de rota.

## Componentes compartilhados (extrair agora, todas as telas reusam)
- **`StatusShape`** (`app/src/components/StatusShape.jsx`): componente que recebe `kind` ("blue" | "green" | "amber" | "red" | "idle") e `size` (opcional). Renderiza a forma CSS correta (círculo/triângulo/losango) usando CSS vars. Implementação: `<span className={`sh ${kind}`} />` com CSS em `theme.css`. Animação pulse em `.sh.blue.pulse`.
- **`Card`** wrapper se quiser; não obrigatório.

## Restrições (RESPEITE TODAS)
1. **ZERO cor hardcoded.** Toda cor sai de `var(--token)`. Se você escrever `#` ou `rgb(` fora de `theme.css`, está errado.
2. **Deps:** React + Vite já instalados (`react`, `react-dom`, `vite`). NÃO adicione novas dependências ao `package.json` sem me consultar. O roteador é client-side manual (pushState), não React Router.
3. **Aditivo:** `painel.py` e `painel.html` atuais NÃO podem ser alterados. O shell React coexiste — o `painel.py` já serve `/dados/*`, o `painel.html` segue funcionando. O Vite roda separado na porta 5173 dev.
4. **Não implementar telas além de Runs e Home.** As outras 18 telas são Tier 1/2/3 futuros. Só sidebar items visuais, sem componente de rota.
5. **CSS onde possível:** prefira classes CSS do design (.eyebrow, .mono, .title, .pill, .btn, .card, .sh, .ni, .zt, .badge, etc.) sobre styled-components/CSS-in-JS. Menos complexidade.
6. **Vite proxy:** se o Vite dev server precisar acessar `/dados/*` no `painel.py` (porta 8378), configure proxy em `vite.config.js`:
   ```js
   server: { proxy: { '/dados': 'http://localhost:8378' } }
   ```
   Isso permite que `fetch('/dados/runs')` funcione no dev server sem CORS.

## DoD (falsificável — o Revisor vai checar cada item)
1. `npm run dev` sobe sem erro. Shell abre no navegador com topbar + sidebar visíveis.
2. Toggle `◐` troca entre escuro e claro — todo o app repinta (cores mudam, nenhum componente fica com cor velha).
3. Clicar em "Runs" na sidebar → main area mostra lista de runs. Clicar em "Home" → mostra placeholder. Navegação entre as duas **não recarrega a página** (verificar no DevTools Network tab — zero full page load).
4. Se `log.jsonl` tem runs (basta rodar `python3 motor_painel/painel.py` antes), a tela Runs mostra dados reais. Se vazio, mostra "Nenhuma run registrada" sem quebrar.
5. `python3 motor_painel/painel.py` sobe sem erro (não quebrou nada no backend).

## Produto final (arquivos que você vai criar/modificar)
```
app/src/theme.css          (NOVO — tokens + temas + tipografia + classes .sh/.btn/.card/.pill/.ni/.zt/.eyebrow/.mono/.title/.badge/.mf-root/.mf-top/.mf-side/.mf-body)
app/src/main.jsx           (EDITAR — ThemeProvider wrapper, inject data-theme, import theme.css)
app/src/index.css          (EDITAR — tirar CSS boilerplate do Vite, deixar só reset body/root mínimo ou merge no theme.css)
app/src/App.jsx            (SUBSTITUIR — layout: Topbar + Sidebar + roteador + Outlet)
app/src/api.js             (NOVO)
app/src/components/Topbar.jsx       (NOVO)
app/src/components/Sidebar.jsx      (NOVO)
app/src/components/StatusShape.jsx  (NOVO)
app/src/routes/Home.jsx    (NOVO — placeholder)
app/src/routes/Runs.jsx    (NOVO — tela de prova viva)
app/vite.config.js         (EDITAR — proxy /dados → localhost:8378)
app/index.html             (EDITAR — title, font links no head)
```

Se houver `App.css` no scaffold, deletar (merge no theme.css).

## Git / commit
- `git add` específico nos arquivos acima (nunca `git add -A`).
- Commit message: `parteB: app shell React — tema, nav, roteador, api.js, tela Runs`

---

**Quando terminar:** avise o Arquiteto com diff + resultado dos testes + como testou cada item do DoD.