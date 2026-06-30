---
tipo: modelo-executor
transporte: opencode
provedor: oc
modelo: qwen/qwen3-coder
permissao: '{"edit":"deny","bash":"deny"}'
capacidades: [codigo]
custo_ordem: 1
---
Coder barato especializado (Qwen3-Coder via OpenCode). Só `codigo`, mas o mais barato —
ganha as tarefas de código sobre os generalistas. Auth: `opencode auth login`; confirme
o id exato com `opencode models` (ajuste `modelo:` se diferir de qwen/qwen3-coder).
