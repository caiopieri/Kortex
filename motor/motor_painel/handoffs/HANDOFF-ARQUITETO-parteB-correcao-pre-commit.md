# Correção — Parte B (pré-commit)

**O que aprovo (não mude):**
- ✅ Hook `usePoll` no `api.js` — é melhor que `startPoll` imperativo. Mantenha.
- ✅ `pages/` no lugar de `routes/` — naming é irrelevante, funciona.
- ✅ Estrutura do App.jsx, Topbar, Sidebar, Runs.jsx — funciona, sem hex hardcoded fora do theme.js.

**O que você DEVE corrigir antes de commitar:**

## 1. theme.js → theme.css (DoD violado)

O handoff exigia **theme.css** como camada ÚNICA de tokens, com CSS vars em CSS (não JS). Motivo: menos runtime JS, mais auditável, bate com o `mf-themes.js` de referência (que injeta `<style>`).

**Como fazer:**
1. Delete `src/theme.js`.
2. Crie `src/theme.css` com as CSS vars nos seletores `.mf-root` (escuro default), `.mf-root[data-theme="stark"]` (claro), e builtins se quiser (`.mf-root[data-theme="gemini"]`, `.mf-root[data-theme="framer"]`).
3. Use os valores exatos do `theme.js` atual — só migre de JS pra CSS.
4. No `App.jsx`, troque:
   ```jsx
   import { applyTheme, getStoredTheme } from './theme.js';
   ```
   por:
   ```jsx
   import './theme.css';
   const THEME_KEY = 'mf-theme-active';
   const getStoredTheme = () => localStorage.getItem(THEME_KEY) || 'paperclip';
   const applyTheme = (id) => {
     document.documentElement.setAttribute('data-theme', id);
     localStorage.setItem(THEME_KEY, id);
   };
   ```
5. O toggle funciona igual — só o mecanismo muda de `root.style.setProperty()` pra `setAttribute('data-theme')` + CSS faz o resto.

**Por quê:** O DoD dizia "ZERO hex hardcoded fora de theme.css". Você colocou no theme.js — funciona, mas quebra a garantia arquitetural de "tokens em CSS, não em JS".

## 2. StatusShape.jsx (débito técnico — pode ficar pra próxima)

Não é crítico — as formas `.sh.blue`, `.sh.green`, etc. já estão no `index.css` e funcionam. Mas o handoff pedia o componente.

**Como fazer:**
- Crie `src/components/StatusShape.jsx`:
  ```jsx
  export default function StatusShape({ kind, size = 9, pulse = false }) {
    const className = `sh ${kind}${pulse ? ' pulse' : ''}`;
    return <span className={className} />;
  }
  ```
- Atualize `Runs.jsx` pra usar `<StatusShape kind={estadoCor(run.estado)} />` no lugar de inline.
- Se não der tempo, marca como `// ponytail: criar StatusShape.jsx component` num comentário no `index.css` e avisa.

## 3. Commit

- `git add src/theme.css src/components/StatusShape.jsx src/App.jsx src/index.css` (específico, nunca `git add -A`).
- Delete `src/theme.js` (`git rm src/theme.js`).
- Commit message: `parteB: app shell React — tema, nav, roteador, api.js, tela Runs (corrige theme.css + StatusShape)`

## 4. Teste antes de commitar

- `npm run dev` sobe sem erro.
- Abre `http://localhost:5173` — toggle `◐` troca tema (todo o app repinta, sem cor velha).
- Navega entre Home e Runs — zero full page reload (DevTools Network tab).
- Se tiver `log.jsonl` com runs, a tela Runs mostra dados vivos.
- `python3 motor_painel/painel.py` sobe sem erro (backend intacto).

**Quando terminar: me avise para eu revisar o diff final antes do commit.**