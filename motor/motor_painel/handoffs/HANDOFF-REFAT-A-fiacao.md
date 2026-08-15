# HANDOFF REFAT-A — Fiação mecânica do painel (bugs 1–9 da auditoria)

> Executor: Codex. Base: `motor/motor_painel/app/src/`. Contexto completo:
> `motor/docs/auditoria/AUDITORIA-PAINEL-TELAS.md`.
> **Toque SOMENTE nestes arquivos** (outros lotes rodam em paralelo em arquivos distintos):
> `pages/MapaGeral.jsx`, `pages/Curador.jsx`, `pages/Datahouse.jsx`, `pages/Logs.jsx`,
> `components/Topbar.jsx`, `components/Sidebar.jsx`, `pages/Board.jsx`, `pages/CaixaFundador.jsx`.
> NÃO tocar: painel.py, api.js, App.jsx, index.css, nenhuma outra página. Não deletar testes.

Contrato da API (não mudar): `GET /dados/agentes` retorna **ARRAY** de
`{id, papel, chamadas, falhas}`. `GET /dados/runs` retorna array de
`{id, objetivo, estado, inicio, custo, n_eventos}`. Eventos reais: ver
`motor/motor/eventos_schema.py` (artefato = **`artefato.atualizou`**).

## Mudanças (todas obrigatórias)

1. **MapaGeral.jsx:50 e Curador.jsx:39** — `Object.entries(agents)` sobre array: trocar por
   `agents.map(a => ...)` usando `a.papel` (fallback `a.id`) como rótulo. Corrigir campo:
   `erros` não existe; usar **`a.falhas`** (manter nome local `erros` só se renomear a leitura).
2. **MapaGeral.jsx:40** — contagem de eventos por projeto: eventos individuais não carregam
   `missao` (só o 1º da run). Substituir por soma de `run.n_eventos` das runs do grupo
   (dado que `/dados/runs` já entrega).
3. **Datahouse.jsx:12** — aceitar o evento real: `['artefato.atualizou', 'artefato.gravado',
   'artefato.atualizado'].includes(ev.evento)`.
4. **Logs.jsx** — (a) timestamp: `ev.t` é segundo relativo (ex.: 0.013), NÃO hora de relógio;
   exibir `t.toFixed(3)+'s'` (formato da timeline do Grafo2D). (b) respeitar
   `localStorage['mf-stream-limit']` (default 50) como máximo de linhas por coluna.
5. **Topbar.jsx** — (a) "+ Nova missão" → `onClick={() => window.location.hash = '/nova-missao'}`;
   (b) sino 🔔 → `'/caixa'`; (c) pill "Projeto: Todos ▾": remover o caret `▾` e o affordance de
   clique (é label estático por ora — não inventar dropdown).
6. **Sidebar.jsx** — (a) adicionar item `Runners` na seção SISTEMA → rota `/runners`;
   (b) remover `sub: true` de Workflows e Datahouse (não são filhos de Grafo 3D; itens de 1º nível).
7. **Board.jsx** — (a) `colFor`: `estado === 'abortada'` → coluna `done` (card já mostra shape
   vermelho + estado); (b) "empurrar p/ produção →" (linha 53): trocar por navegação real
   `window.location.hash = '/nova-missao'`; (c) "arquivar" (linha 61): implementar local com
   `localStorage['mf-board-arquivadas']` (array de ids; cards arquivados não renderizam) —
   OU remover o botão; escolher UM, sem meio-termo morto; (d) "promover →" das Ideias: mover o
   card para a coluna Planejamento como candidato local (não apenas deletar).
8. **CaixaFundador.jsx:485** — "Abrir Mapa geral" → `'/mapa'` (hoje vai pra `/grafo`).
9. **CaixaFundador.jsx** — feedback pós-decisão: após `postGateDecision` OK, marcar o gate
   localmente como "decisão registrada · aguardando motor" (estado local; o card real some quando
   o log emitir `decisao.fundador`). Sem inventar evento.

## DoD (falsificável)
- `cd motor/motor_painel/app && npm run build` verde.
- `grep -n "Object.entries(agents)" src/pages/*.jsx` → 0 resultados.
- `grep -n "artefato.atualizou" src/pages/Datahouse.jsx` → ≥1.
- Topbar: 3 handlers presentes; Sidebar tem `/runners`.
- Nenhum arquivo fora da lista tocado; nenhum teste deletado.
- Relatar em `motor/motor_painel/handoffs/RELATO-REFAT-A.md`: o que mudou por arquivo + saída do build.
