# Item 3B - Frente E - matriz 2x2 especialista pequeno

Data dos runs: 2026-07-04

Modelos/provedores sob teste:

- Pequeno: `codex/gpt-5.4-mini`
- Generalista maior nao-Claude: `codex/gpt-5.4`

Todos os runs foram executados em cwd temporario fora do repo; nos bracos COM RAG, o cwd continha apenas a copia do JSONL usado como fonte.

Nota de custo: os tokens sao estimados localmente por caracteres/4 via `ClienteUsoEstimado`. USD so foi calculado para `codex/gpt-5.4-mini`, porque `exemplos/precos-especialista-ab.json` nao tem preco local para `codex/gpt-5.4`.

## Tarefa 1 - CSV para JSON (`especialista-csv-json.json`)

| celula | aprovacao | latencia p50 | latencia p90 | tokens/run | prompt/run | completion/run | USD/run |
|---|---:|---:|---:|---:|---:|---:|---:|
| pequeno SEM RAG | 5/5 | 8.409s | 8.709s | 288 | 221 | 67 | 0.00018925 |
| pequeno COM RAG | 5/5 | 8.201s | 13.929s | 504 | 437 | 67 | 0.00024325 |
| generalista SEM RAG | 5/5 | 8.602s | 14.154s | 288 | 221 | 67 | n/d |
| generalista COM RAG | 5/5 | 8.144s | 8.241s | 504 | 437 | 67 | n/d |

Rodadas cruas:

| celula | r1 | r2 | r3 | r4 | r5 |
|---|---:|---:|---:|---:|---:|
| pequeno SEM RAG | ok 7.392s | ok 8.709s | ok 8.592s | ok 8.333s | ok 8.409s |
| pequeno COM RAG | ok 13.929s | ok 10.673s | ok 8.201s | ok 7.175s | ok 7.312s |
| generalista SEM RAG | ok 8.711s | ok 8.602s | ok 8.439s | ok 14.154s | ok 7.964s |
| generalista COM RAG | ok 8.144s | ok 8.220s | ok 8.241s | ok 8.002s | ok 7.748s |

Leitura: o pequeno passa ate SEM RAG. Nesta tarefa, o ganho do item 13 nao pode ser atribuido a RAG; e roteamento por tier/modelo em tarefa mecanica.

## Tarefa 2 - fatos nao-adivinhaveis (`lift-v3-fatos.json`)

| celula | aprovacao | latencia p50 | latencia p90 | tokens/run | prompt/run | completion/run | USD/run |
|---|---:|---:|---:|---:|---:|---:|---:|
| pequeno SEM RAG | 5/5 | 28.988s | 41.870s | 353 | 322 | 31 | 0.00014250 |
| pequeno COM RAG | 5/5 | 29.760s | 44.510s | 3086 | 3040 | 46 | 0.00085200 |
| generalista SEM RAG | 5/5 | 19.982s | 26.961s | 346 | 322 | 24 | n/d |
| generalista COM RAG | 2/5 | 20.434s | 314.264s | 3078 | 3040 | 38 | n/d |

Rodadas cruas:

| celula | r1 | r2 | r3 | r4 | r5 |
|---|---:|---:|---:|---:|---:|
| pequeno SEM RAG | ok 41.870s | ok 25.380s | ok 28.680s | ok 33.727s | ok 28.988s |
| pequeno COM RAG | ok 43.297s | ok 27.053s | ok 23.576s | ok 44.510s | ok 29.760s |
| generalista SEM RAG | ok 26.106s | ok 26.961s | ok 18.703s | ok 19.982s | ok 18.726s |
| generalista COM RAG | falha 314.264s | ok 31.278s | falha 12.423s | ok 20.434s | falha 16.272s |

Nas falhas do `generalista COM RAG`, o validador `contem` registrou `presentes 0/4` e faltantes: `auto_esgotar`, `aresta.fluxo`, `custo.tick`, `sem_secrets_no_diff`, `teste_permissao_cross_tenant`.

## Leitura pre-registrada

A tese "especialista barato + RAG" **nao avanca** nesta matriz:

- Na tarefa 1, o pequeno SEM RAG ja resolve tudo: isso mede tier/roteamento, nao RAG.
- Na tarefa 2, o pequeno SEM RAG tambem passou 5/5. Portanto o ganho nao pode ser atribuido a RAG.
- O pequeno COM RAG foi mais caro em tokens que o pequeno SEM RAG na tarefa 2 (3086 vs 353 tokens/run estimados), sem ganho de aprovacao.
- O generalista COM RAG foi instavel nesta amostra (2/5, com uma rodada de 314.264s), apesar de usar o corpus relevante.

Resultado bruto: inconclusivo/negativo para a tese especialista barato + RAG. O achado mais forte e que `lift-v3-fatos` ainda nao e uma boa tarefa para separar "sem conhecimento" na matriz E quando o sujeito e Codex CLI; o SEM RAG passou 5/5 mesmo isolado do repo.
