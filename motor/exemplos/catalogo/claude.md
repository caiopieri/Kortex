---
tipo: modelo-executor
transporte: claude-cli
padrao: true
capacidades: [codigo, redacao, calculo, pesquisa, raciocinio-longo]
custo_ordem: 10
auto_esgotar: true
---
Claude como ÚLTIMO recurso (padrao/fallback). custo_ordem 10 = mais caro, só entra
se tudo abaixo na escada falhar. `auto_esgotar: true` liga o failover em cadeia do motor
(provedor que falha é pulado no resto da missão; desce/sobe a escada por custo).
Reservado — na prática só roda se NVIDIA e Codex caírem.
