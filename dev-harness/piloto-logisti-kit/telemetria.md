# Telemetria do piloto — Logisti / Rota Forja sob regime barato

> Preencher UMA LINHA POR FASE, na hora (não de memória depois). É isto que torna o
> piloto um experimento e não um passeio. Vai para `docs/telemetria.md` no repo.

| Fase                      | Modelo          | Início | Fim   | Retrabalho? (o quê)                                                                                                             | Gate pegou erro? (qual)                                                                                                       | Nota 1-5 |
| ------------------------- | --------------- | ------ | ----- | ------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- | -------- |
| constitution              | kimi-k2.6       | 14:20  | 14:28 | Sim, criou em docs/ inves de .specify/memory/; mandei mover                                                                     | Sim, claude em review externo pegou o local errado                                                                            | 4        |
| specify                   | kimi-k2.6       | 14:34  | 14:38 | Não                                                                                                                             | Não                                                                                                                           | 5        |
| clarify                   | kimi-k2.6       | 14:43  | 14:50 | Apenas por acabar o limite                                                                                                      | Não                                                                                                                           | 4        |
| plan                      | kimi-k2.6       | 14:50  | 14:53 | Exceto por acabar o limite, a nvidia barrou por algumas horas                                                                   | Não                                                                                                                           | 4        |
| revisão do plano (humano) | caio (+claude?) | 14:53  | 14:54 | São muitas coisas, não encontrei erros por extensão                                                                             | Não sei                                                                                                                       | 4        |
| tasks                     | kimi-k2.6       |        |       | Nenhum problema, exceto acabar os tokens, nvidia api gratis limitou excesso de requisições e via openrouter consumiu 4 dólares. | Claude assumiu daqui para frente pois orçamento de 4 dolares esgotou, mais de 11 milhões de tokens gastos apenas para 7 tasks | 3        |
| analyze                   | kimi-k2.6       |        |       |                                                                                                                                 |                                                                                                                               |          |
| checklist                 | kimi-k2.6       |        |       |                                                                                                                                 |                                                                                                                               |          |
| implement                 | kimi-k2.6       | 18:29  | 18:29 |                                                                                                                                 |                                                                                                                               |          |
| revisão do diff (humano)  | caio            | 19:30  | 20:00 | Todos os testes passaram                                                                                                        | Claude aprovou                                                                                                                | 4        |

## Escalações (se houver)

| Tarefa | Falhou como (2-3 tentativas?) | Escalada para | Resultado |
|---|---|---|---|

## Kill criteria (responder no fim, honestamente)

1. Menos retrabalho do que seria sem harness? (baseline finance-sim: sim)
2. O gate do plano pegou mais erro que o do diff? (baseline: sim)
3. A fatia saiu funcionando com testes no caminho crítico?

Veredito: [ ] Rota Forja → L1 (regime barato/kimi) | [ ] Falhou na fase ___ → re-rodar só ela com Claude | [x] excesso de tokens consumidos, falta alguma melhoria nesse quesito.
