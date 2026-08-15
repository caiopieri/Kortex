# Tasks — onda 1 do hardening

Status: **CONCLUIDA**  
Escopo aprovado: `H03`, `H06a`, depois `H10a`; no maximo duas frentes.

## Regras

- Cada owner executa seus nodeids com `landing=owner_pr` por `tests/audit_corpus.py`;
  oraculo migrado permanece no corpus e exige `replacement_nodeid` executavel.
- H03 e H06a nao compartilham arquivo e podem avancar em paralelo. H10a inicia depois que
  uma delas fechar.
- Nenhum tratamento de comando H04/H05, payload `curador.*` H06b, recovery/seq H07,
  ledger/outbox H10b ou idempotencia de resume H11.
- Cada PR: producao + testes em aproximadamente 300 linhas ou menos, sem `skip`/`xfail`.

## H03 — falha parcial e dependencias

- [x] **W1-T001 — Normalizar excecoes do executor e verifier**
  - Arquivos: `motor/motor/grafo.py`, `motor/tests/test_hardening_h03.py`.
  - Capturar falha por tentativa na fronteira correta, emitir `executor.erro` sem dado
    sensivel e produzir resultado reprovado deterministico. Nao capturar `BaseException`.
  - Preservar retry/tier e diferenciar executor sem resposta de excecao.
- [x] **W1-T002 — Bloquear dependente de resultado reprovado**
  - Arquivos: `motor/motor/grafo.py`, `motor/tests/test_hardening_h03.py`.
  - No DAG, dependencia reprovada nunca entra no prompt nem autoriza chamada do dependente;
    o no bloqueado vira resultado reprovado auditavel, sem travar a ordenacao.
  - Nao reimplementar a reconciliacao nem alterar seu teto.
- [x] **W1-T003 — Gate H03**
  - Executar 4 nodeids H03 vigentes, a regressao substituta de K2, controles de retry/DAG
    e suite rastreada.
  - Security-DoD Universal + Bot/LLM; erro externo nao vaza stack/prompt.

## H06a — envelope de evento v2

- [x] **W1-T004 — Fechar envelope e payload runtime**
  - Arquivos: `motor/motor/eventos_schema.py`, `motor/tests/test_hardening_h06a.py`.
  - Declarar campos obrigatorios, tipos estritos, campos permitidos e reservados para os
    tipos atuais. `evento`, tempo e futuros campos de sequencia pertencem ao writer.
  - Nao adicionar `curador.*`; isso pertence a H06b.
- [x] **W1-T005 — Validar antes do append**
  - Arquivos: `motor/motor/eventos.py`, `motor/tests/test_hardening_h06a.py`.
  - Tipo desconhecido, payload incompleto/extra/tipado errado ou colisao com envelope falha
    antes de qualquer byte ser escrito.
  - Nao mudar append/reabertura, relogio, lock ou JSON estrito; pertencem a H07.
- [x] **W1-T006 — Gate H06a**
  - Executar 7 nodeids H06a vigentes, a regressao substituta de E1, guard anti-drift e
    suite rastreada.
  - Security-DoD Universal; JSONL e payload sao input hostil.

## H10a — contrato de nota e decisao

- [x] **W1-T007 — Validar nota, IDs, opcoes e decisao**
  - Arquivos: `motor/motor/caixa.py`, `motor/tests/test_hardening_h10a.py`.
  - Portao/arquivo ficam presos a caixa; nota parcial ou texto externo nao autoriza gate;
    decisao deve pertencer as opcoes persistidas.
- [x] **W1-T008 — Deadline e nomes sem colisao**
  - Arquivos: `motor/motor/caixa.py`, `motor/tests/test_hardening_h10a.py`.
  - Poll nunca dorme alem do deadline monotonic; timeout preserva nota; arquivos decididos
    recebem identidade unica mesmo no mesmo segundo.
- [x] **W1-T009 — Validar `job_id` operacional**
  - Arquivos: `motor/motor/servico.py`, `motor/tests/test_hardening_h10a.py`.
  - Rejeitar `.`/`..`, separadores, traversal e dominio fora do ID canonico.
  - Nao antecipar claim concorrente, SQLite ledger ou resume idempotente.
- [x] **W1-T010 — Gate H10a e onda 1**
  - Executar os 7 nodeids H10a, H03/H06a, suite rastreada e registrar o Gate CI global.
  - Security-DoD Universal + paths; banco e concorrencia ficam para H10b/H11.

## Onde isto pode dar errado

- Um `except Exception` largo em torno do no inteiro pode esconder bug de programacao; limitar
  captura as chamadas externas e manter erro interno visivel.
- Exigir schema v2 sem separar H07 pode truncar/reordenar logs; H06a so valida antes do write.
- Fazer arquivos da Caixa parecerem transacionais anteciparia uma garantia falsa antes do
  ledger/outbox de H10b.
