# Verificacao - H07 ledger JSONL e projecao

Status: **CONCLUIDA NO ESCOPO H07a-H07e**
Data: 2026-07-12
Ambiente de teste: CPython 3.11.15

## Discovery E Contrato

Duas passagens fresh usaram Graphify e leram integralmente apenas
`motor/motor/eventos.py`, `motor/motor/eventos_schema.py` e
`motor/motor_painel/painel.py`. A segunda passagem foi adversarial e encontrou cinco
defeitos adicionais reproduziveis antes do fechamento.

- O writer v2 usa sidecar persistente, `flock` nao bloqueante e abertura sem seguir links;
  arquivo nao regular, hardlink e troca de inode falham fechado
  (`motor/motor/eventos.py:31`, `motor/motor/eventos.py:87`).
- Arquivo e entrada de diretorio sao sincronizados na criacao
  (`motor/motor/eventos.py:118`).
- Replay exige schema v2, `seq` contigua e tempo nao regressivo; v1 permanece somente
  leitura (`motor/motor/eventos.py:134`).
- Tail parcial e preservado byte a byte em quarentena duravel antes de qualquer truncate
  (`motor/motor/eventos.py:174`).
- Antes de cada append, o writer confirma que o pathname ainda referencia o inode aberto;
  falha fecha log e sidecar (`motor/motor/eventos.py:202`).
- Evento e validado e serializado como JSON estrito antes de write; flush e fsync antecedem
  o avanco de `seq` em memoria (`motor/motor/eventos.py:213`).
- O painel aceita v1 para visualizacao, mas remove v1 antes de projetar gates; POST baseado
  somente em v1 retorna 404 e nao cria SQLite (`motor/motor_painel/painel.py:271`).
- V2 no painel exige JSON estrito, schema, sequencia e tempo; somente o ultimo fragmento sem
  newline e ignorado (`motor/motor_painel/painel.py:74`, `motor/motor_painel/painel.py:87`).

## Governanca Dos Reprodutores

Dois oraculos congelados contradiziam contratos ja aprovados e permanecem preservados no
manifest, mas nao pousam:

- append autoritativo em v1: `rejected_contract/not_landed`, porque v1 e read-only;
- evento sem payload H06a: `rejected_contract/not_landed`.

`tests.audit_corpus.casos` agora seleciona apenas dispositions autorizadas. O wrapper H07
fixa em quatro os reprodutores autoritativos restantes.

## Evidencia Causal

| Fatia | Garantia principal | Teste |
|---|---|---|
| H07a | append, lock, seq, tempo, JSON/fsync | `motor/tests/test_hardening_h07a.py` |
| H07b | quarantine e tail parcial | `motor/tests/test_hardening_h07b.py` |
| H07c | sidecar, links, fsync dir, cleanup, seq >= 1 | `motor/tests/test_hardening_h07c.py` |
| H07d | v1 sem autoridade; v2 semantico no painel | `motor/tests/test_hardening_h07d.py` |
| H07e | replace/unlink/hardlink tardio antes do append | `motor/tests/test_hardening_h07e.py` |
| Manifest | quatro casos H07 autoritativos | `motor/tests/test_hardening_h07.py` |

## Gate Da Fatia

| Checagem | Resultado |
|---|---|
| H07a-H07e + manifest + schema + painel/despacho | `96 passed` |
| H07 + H06a/schema focado | `54 passed` |
| Manifest integro e dispositions validas | passou |
| Ruff | limpo |
| mypy | limpo |
| Bandit high/high | limpo |
| compileall | limpo |
| Diff H07a/H07b/H07c/H07d/H07e | cada landing abaixo de 300; H07c = 298 |

O Gate CI, overlay bruto e build/install do snapshot final serao repetidos depois das fatias
restantes. Este documento nao declara o motor pronto para producao.

## Security DoD

- Path final nao segue symlink e arquivo com mais de um link e recusado.
- Lock, arquivo, quarantine e diretorio possuem ordem explicita de durabilidade.
- Falha de write, fsync ou unlock libera descritores e impede reutilizar estado ambiguo.
- Input JSON v2 e hostil: constante nao finita, payload invalido, gap, duplicata e regressao
  falham fechado.
- V1 nao autoriza gate, replay ou decisao operacional.

## Onde isto pode dar errado

- `lstat` e `write` nao formam uma operacao atomica. O contrato depende de diretorio pai
  confiavel e nao gravavel por atacante; o writer documenta, mas nao cria essa permissao.
- `flock` e durabilidade variam em NFS/filesystems remotos. A suite prova chamadas e ordem,
  nao substitui crash test no filesystem do deployment.
- Writer e painel ainda carregam o ledger inteiro em memoria; rotacao/migracao auditada e
  necessaria antes de logs crescerem sem limite.
- Queda apos quarantine duravel e antes de truncate pode criar quarantine duplicada no
  restart. Os bytes permanecem preservados, mas a operacao exige runbook.
