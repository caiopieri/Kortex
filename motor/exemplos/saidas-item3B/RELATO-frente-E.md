# Item 3B - Frente E - matriz 2x2 especialista pequeno

Corrigido em 2026-07-04. O relato anterior desta frente foi suspenso porque a coleta não estava isolada de forma auditável. A versão abaixo é a reprodução com isolamento estrutural no script.

Data dos runs: 2026-07-04

Modelos/provedores sob teste:

- Pequeno: `codex/gpt-5.4-mini`
- Generalista maior nao-Claude: `codex/gpt-5.4`

Todos os runs foram executados em cwd temporario fora do repo; o script imprime e valida esse cwd por célula. Nos bracos COM RAG, o cwd continha apenas a copia do JSONL usado como fonte.

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

## Tarefa 2 - fatos nao-adivinhaveis (`lift-v3-fatos.json`, isolada)

| celula | aprovacao | latencia p50 | latencia p90 | tokens/run | prompt/run | completion/run | USD/run |
|---|---:|---:|---:|---:|---:|---:|---:|
| pequeno SEM RAG | 0/5 | 45.809s | 303.389s | 353 | 322 | 31 | 0.00014250 |
| pequeno COM RAG | 2/5 | 47.107s | 396.022s | 3086 | 3040 | 46 | 0.00085200 |
| generalista SEM RAG | 0/5 | 40.676s | 44.082s | 346 | 322 | 24 | n/d |
| generalista COM RAG | 0/5 | 36.452s | 52.175s | 3078 | 3040 | 38 | n/d |

Rodadas cruas:

| celula | r1 | r2 | r3 | r4 | r5 |
|---|---:|---:|---:|---:|---:|
| pequeno SEM RAG | falha 303.389s | falha 40.398s | falha 47.107s | falha 45.809s | falha 44.900s |
| pequeno COM RAG | falha 35.510s | falha 47.107s | ok 49.455s | ok 396.022s | falha 35.424s |
| generalista SEM RAG | falha 40.247s | falha 39.319s | falha 41.519s | falha 40.676s | falha 44.082s |
| generalista COM RAG | falha 33.725s | falha 36.146s | falha 52.175s | falha 36.646s | falha 36.452s |

Evidência de isolamento por célula:

| celula | cwd | ls |
| --- | --- | --- |
| pequeno SEM RAG | `/private/var/folders/k8/pp6b77px7xx16bx55wd3mkz40000gn/T/item3B-pequeno_sem_rag-8v4ikgyg` | `(vazio)` |
| pequeno COM RAG | `/private/var/folders/k8/pp6b77px7xx16bx55wd3mkz40000gn/T/item3B-pequeno_com_rag-8_qqpjqk` | `fonte.jsonl` |
| generalista SEM RAG | `/private/var/folders/k8/pp6b77px7xx16bx55wd3mkz40000gn/T/item3B-generalista_sem_rag-qjcm9aur` | `(vazio)` |
| generalista COM RAG | `/private/var/folders/k8/pp6b77px7xx16bx55wd3mkz40000gn/T/item3B-generalista_com_rag-7mflfiz8` | `fonte.jsonl` |

Nas falhas do `pequeno COM RAG`, o validador `contem` registrou `presentes 0/4` em duas rodadas e `presentes 5/5` em duas rodadas; no agregado da célula, a aprovação ficou em 2/5. Nas falhas do `generalista COM RAG`, o validador `contem` registrou `presentes 0/4` e faltantes: `auto_esgotar`, `aresta.fluxo`, `custo.tick`, `sem_secrets_no_diff`, `teste_permissao_cross_tenant`.

## Leitura pre-registrada

A tese "especialista barato + RAG" **nao avanca** nesta reprodução isolada:

- Na tarefa 1, o pequeno SEM RAG ja resolve tudo: isso continua medindo tier/roteamento, nao RAG.
- Na tarefa 2, a reproducao isolada derruba o `pequeno SEM RAG` para 0/5 e o `pequeno COM RAG` para 2/5.
- O `pequeno COM RAG` continua mais caro em tokens que o `pequeno SEM RAG` na tarefa 2 (3086 vs 353 tokens/run estimados), sem bater o piso 4/5.
- O `generalista COM RAG` ficou em 0/5 nesta reproducao isolada.

Resultado bruto: **negativo/inconclusivo para a tese especialista barato + RAG**. A reproduçao isolada contradiz o relato anterior e passa a ser o dado valido. A tarefa 2 ainda não separa bem os braços quando o sujeito é Codex CLI; o efeito de RAG não fecha o critério pré-registrado.
