# HANDOFF REFAT-B — Grafo 3D real + tema; Grafo 2D sem teatro

> Executor: subagente Claude. Base: `motor/motor_painel/app/src/`. Contexto:
> `motor/docs/auditoria/AUDITORIA-PAINEL-TELAS.md`.
> **Toque SOMENTE**: `pages/Grafo3D.jsx`, `pages/Grafo2D.jsx`.
> NÃO tocar: api.js, App.jsx, index.css, outras páginas (lotes A e C rodam em paralelo).

## Grafo3D.jsx
1. **Ligar ao dado real**: substituir `rawGraphData` (linhas 72–95, mock "Logisti-Kit",
   "clientes.db", "86% 1ª aprovação"…) por grafo derivado de `fetchDados()` (já buscado e
   ignorado): nós de `data.nos` (`{id, tipo}` com tipo ∈ nucleo/executor/subagente/portao/decisor),
   arestas de `data.arestas` (`{de, para}`). Tamanho do nó por grau; cor por `tipo`.
   Runs ativas/custo continuam vindos de runs (linhas 69–70). Camada "macro" = nucleo+portao+decisor.
2. **Tema**: eliminar cores hardcoded (`#060708`, `#E8E6E1`, `#5B7FE8`, `0x…`, rgba fixos —
   linhas ~135–215, 331–371). Ler do tema: helper
   `cssVar(n) => getComputedStyle(document.documentElement).getPropertyValue(n)` para
   `--bg, --text, --text3, --border, --blue, --green, --amber, --surface`; aplicar em
   backgroundColor, labels, links, partículas, legendas e luzes. Recalcular quando
   `data-theme` do `.mf-root` mudar (MutationObserver ou verificação no tick) — no tema claro
   o canvas TEM de ficar claro.
3. Manter controles existentes (macro/completo, pausar física, fluxo, slider, ← 2D) funcionando.

## Grafo2D.jsx
4. **Remover controles mortos**: pill "✎ Edição" (719), pill "filtro: workflow ▾" (702),
   bloco "Chat do nó · 3 modos" + pills Enfileirar/Direcionar/Perguntar + falso input
   "Injeta um prompt ou anexo…" (812–819). Remover, não esconder.
5. **Replay honesto**: hoje só congela o poll (716). Renomear para "⏸ pausar" (e o indicador
   correspondente), OU implementar scrub real na timeline. Escolher UM.
6. **Metadata fabricada fora**: mapa hardcoded de modelos por nó ("planner · kimi-k2.6",
   "evaluator · codex/gpt-5.4", "HF · RAG · 6 chunks" — linhas 214–263) → derivar modelo real por
   executor dos eventos `modelo.uso` (`ev.executor`, `ev.modelo`); sem evento → omitir a linha.
7. **Custo por nó**: tabela de preços inventada `p_in/p_out` (325–343) → exibir **tokens reais**
   (soma de `modelo.uso` por executor: `prompt_tokens+completion_tokens`) em vez de US$; sem
   evento → omitir.
8. **"Alterações · últimos arquivos"** hardcoded (`plano.md +64 −0`… linhas 356–364) → derivar de
   eventos `artefato.atualizou` (campo `artefato`/`caminho`) do executor; senão "nenhum arquivo
   registrado".
9. **runId fallback** `'RUN-2026-07-02-013'` (594) → `'—'`. Header da tela: o grafo agrega TODAS
   as runs do log; trocar o rótulo do nome de run única por "todas as runs · N" (N real) — não
   fingir que é uma run só.

## DoD (falsificável)
- `cd motor/motor_painel/app && npm run build` verde.
- `grep -nE "kimi-k2\.6|RUN-2026-07-02|Logisti-Kit|clientes\.db|plano\.md" src/pages/Grafo2D.jsx src/pages/Grafo3D.jsx` → 0.
- `grep -nE "#[0-9A-Fa-f]{6}|0x[0-9A-Fa-f]{6}" src/pages/Grafo3D.jsx` → 0 (exceto se dentro de comentário justificando).
- Relatar em `motor/motor_painel/handoffs/RELATO-REFAT-B.md`.
