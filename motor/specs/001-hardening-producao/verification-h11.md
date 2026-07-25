# Verificacao - H11 consumer, dedupe e resume

Status: **CONCLUIDA NO ESCOPO H11**
Data: 2026-07-12
Ambiente de teste: CPython 3.11.15

## Discovery E Contrato

Graphify foi executado antes da leitura integral de `motor/motor/caixa.py` e
`motor/motor/servico.py`:

```text
graphify query "Como LedgerCaixa, outbox H10b e o fluxo real de decisao/resume em
ServicoOrquestrador se conectam, e onde H11 deve implementar claim/ack e dedupe
persistente por decision_id?" --budget 1800
```

O mapa nao continha os simbolos novos de H10/H11; os cinco nodeids do manifest foram
ligados causalmente ao ledger, ao arquivo da Caixa, ao snapshot LangGraph e ao servico.

- `ack` usa CAS por owner, versao e lease vivo. `APPLIED` e um owner reservado que nao
  pode ser fornecido pela API; o contador maximo continua confirmavel sem colidir com o
  tombstone (`motor/motor/caixa.py:292`).
- `consumir` relê o claim vivo antes do callback e rejeita payload mutado. A entrega e
  at-least-once: o callback deve deduplicar o efeito por `decisao_id`
  (`motor/motor/caixa.py:342`).
- Claim usa exclusao correlacionada por `job_id` dentro do mesmo `BEGIN IMMEDIATE`:
  existe no maximo um lease vivo por job, mas jobs distintos continuam paralelos
  (`motor/motor/caixa.py:217`).
- `rodar_com_caixa` exige `thread_id` valido antes de reivindicar qualquer outbox, registra
  a decisao antes de arquivar a nota e retoma com mapa por ID
  (`motor/motor/caixa.py:571`).
- `GerenciadorJobs` reconcilia a outbox em worker proprio depois de restart, sem tornar
  `status()` mutante; poll, lease e shutdown possuem contrato explicito
  (`motor/motor/servico.py:64`).
- `responder_gate` valida interrupts por snapshot e conexao separados. Multiplos gates
  exigem `decision_id`; `status` expoe `gates` e preserva `gate` como alias do primeiro
  (`motor/motor/servico.py:154`).
- Respostas identicas ja `PENDING|CLAIMED|APPLIED` sao aceitas idempotentemente. Conteudo,
  job ou ID divergente falha fechado.

## Evidencia Causal

`motor/tests/test_hardening_h11.py` cobre:

| Garantia | Evidencia |
|---|---|
| Cinco reprodutores congelados H11 | `test_reprodutor_h11` |
| Ack exige owner, versao e lease vivo | `test_ack_exige_owner_versao_e_lease_vivo` |
| Config sem thread nao captura outro job | `test_runner_sem_thread_id_nao_reivindica_decisao_de_outro_job` |
| Poll, lease, IDs e lifecycle falham cedo | `test_config_outbox_invalida_falha_antes_de_criar_worker` |
| Shutdown nao fecha SQLite com worker vivo | `test_fechar_nao_fecha_conexao_com_job_vivo_e_bloqueia_mutacoes` |
| Processo morre apos claim/aplicar/ack e converge | `test_crash_em_cada_fronteira_converge_apos_restart` |
| Restart do servico reconcilia sem nova resposta | `test_servico_reconcilia_automaticamente_apos_restart_de_processo` |
| Um lease vivo por job, jobs diferentes paralelos | `test_claim_serializa_mesmo_job_e_mantem_jobs_distintos_paralelos` |
| Redelivery exige efeito idempotente por ID | `test_lease_expirado_redelivera_mas_efeito_deduplica_por_decision_id` |
| Claim mutado nao chega ao callback | `test_consumer_rejeita_claim_mutado_antes_do_efeito` |
| MAX nao colide com APPLIED | `test_lease_maximo_ainda_pode_ser_confirmado_sem_colidir_com_applied` |
| Duas instancias aplicam uma resposta sob lease vivo | `test_servico_real_concorrente_persiste_decision_id_e_ack` |
| Dois interrupts mantem IDs e resumes serializados | `test_servico_serializa_dois_interrupts_paralelos_por_job` |

O teste de dois interrupts foi repetido em cinco processos pytest independentes; todos
passaram. Durante o primeiro callback ha exatamente uma outbox `CLAIMED` e uma `PENDING`;
depois do ack, o reconciliador aplica a segunda e ambas terminam `APPLIED`.

## Gate

| Checagem | Resultado |
|---|---|
| H11 isolado | `26 passed` |
| Cinco nodeids manifest H11 | `5 passed` |
| H10a/H10b/Caixa/Servico | `52 passed` |
| Suite versionada | `345 passed` |
| Suite versionada + hardening | `490 passed` |
| Pack completo como overlay | `73 passed, 38 failed` |
| Ruff CI (`ruff check motor/`) | limpo |
| mypy CI (`mypy motor/`) | limpo, 72 arquivos |
| Bandit high/high | limpo |
| compileall | limpo |
| Gitleaks dir (`motor/`) | limpo, 16.91 MB |
| build sdist/wheel | passou |
| install e smoke do wheel isolado | passou; claims por job e shutdown |

Build final: `/tmp/orquestrador-h11-final-build.E33kxm`.
Install final: `/tmp/orquestrador-h11-final-install.OiTZH1`.

As 38 falhas do overlay pertencem a H05, H07, H08/H09 e oraculos congelados com
disposicao registrada. Nenhum caso H11 permanece vermelho. Esta verificacao nao declara o
Gate CI global aprovado nem o motor pronto para producao.

## Security DoD

- SQL externo continua parametrizado; o SQL dinamico de claim contem somente fragmentos
  internos e valores entram por placeholders.
- IDs, duracoes, payload persistido e claims sao validados antes de efeito.
- Escritores usam `BEGIN IMMEDIATE`; claim, exclusao por job e ack sao transicoes CAS.
- Processo real e encerrado nos pontos de falha e o restart prova liveness.
- SAST, secrets, tipos, lint e compilacao estao limpos.

H13 restaurou o documento canonico em `motor/docs/security-DoD.md`. Os gates H11 acima foram
executados antes dessa restauracao usando as regras do AGENTS; o novo checklist nao altera
os resultados historicos nem declara o gate global aprovado.

## Tamanho E Landing

H11 deve pousar em revisoes separadas; nao transformar o working tree atual em um PR unico:

- H11a: ack, validacao do claim, fault boundaries e redelivery idempotente.
- H11b: integracao Caixa/Servico e respostas concorrentes.
- H11c: reconciliador automatico, configuracao e lifecycle/shutdown.
- H11d: exclusao por job, multiplos interrupts e protocolo `decision_id`.

H11d ficou em 291 insercoes e 4 remocoes (295 linhas alteradas). Cada landing precisa
carregar seus testes causais e manter o gate consolidado verde.

## Onde isto pode dar errado

- Lease vencendo durante `grafo.invoke` permite redelivery; efeitos externos precisam de
  chave idempotente duravel. H11 nao promete exactly-once entre stores diferentes.
- O lease pressupoe relogio de parede coerente no mesmo host. NTP/skew e WAL sobre NFS nao
  fazem parte do contrato.
- O reconciliador guarda a ultima excecao internamente, mas ainda nao expoe endpoint de
  saude; H13 deve tornar essa divida observavel.
- Callers de `GerenciadorJobs` precisam chamar `fechar()`. Daemon e apenas protecao de
  compatibilidade, nao lifecycle de producao.
- O fallback sem IDs existe somente para o oracle legado e nao deve ser ampliado para novos
  clientes.
- O build foi produzido de checkout sujo e incluiu testes de auditoria nao rastreados; a
  release H13 deve ser reconstruida de checkout limpo.
