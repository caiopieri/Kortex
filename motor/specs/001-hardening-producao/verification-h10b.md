# Verificacao - H10b ledger, outbox e lease

Status: **CONCLUIDA NO ESCOPO H10b**
Data: 2026-07-12
Ambiente de teste: CPython 3.11.15

## Contrato Entregue

- `LedgerCaixa` exige SQLite >= 3.35, arquivo persistente, WAL, foreign keys e
  `synchronous=FULL`; configuracao inferior falha fechada
  (`motor/motor/caixa.py:40`).
- O schema namespaced `caixa_meta` v1 evita conflitar com metadados do checkpointer e
  rejeita schema legado/desconhecido sem tentar migracao implicita
  (`motor/motor/caixa.py:60`).
- `caixa_ledger` e `caixa_outbox` sao gravados na mesma transacao `BEGIN IMMEDIATE`.
  Reentrada com o mesmo `decisao_id` e conteudo e estavel; conteudo divergente falha
  (`motor/motor/caixa.py:168`).
- Claim usa `UPDATE ... RETURNING` dentro da transacao, concede somente item sem lease ou
  expirado e incrementa `lease_version` (`motor/motor/caixa.py:214`).
- Renovacao usa CAS por outbox, owner e versao; nao encurta lease, nao aceita lease expirado
  e bloqueia overflow de inteiro SQLite (`motor/motor/caixa.py:235`).
- Clock e prazo sao finitos, o prazo precisa avancar representavelmente e o clock so e lido
  depois de obter o lock de escrita.

`motor/motor/servico.py` nao recebeu delta H10b. Integrar o consumer ao resume antes de
deduplicacao criaria a janela de crash que H11 deve fechar.

## Evidencia Causal

O manifest congelado nao possui casos `owner=H10b`; esta fatia adicionou doze testes causais
com SQLite real em `motor/tests/test_hardening_h10b.py`:

| Garantia | Evidencia |
|---|---|
| Falha entre ledger/outbox faz rollback total | `motor/tests/test_hardening_h10b.py:38` |
| Duas conexoes concedem no maximo um lease | `motor/tests/test_hardening_h10b.py:61` |
| Lease vivo/expirado e CAS de owner/versao | `motor/tests/test_hardening_h10b.py:81` |
| Clock e lido depois do lock real | `motor/tests/test_hardening_h10b.py:106` |
| IDs, conflito e overflow falham fechados | `motor/tests/test_hardening_h10b.py:148` |
| Reabertura preserva ledger/outbox | `motor/tests/test_hardening_h10b.py:187` |
| `os._exit` entre inserts recupera `(0,0)` e DB integra | `motor/tests/test_hardening_h10b.py:200` |
| Schema legado/futuro e recusado | `motor/tests/test_hardening_h10b.py:216` |
| Memoria, prazo sem progresso e inteiros gigantes sao recusados | `motor/tests/test_hardening_h10b.py:230` |

O primeiro subagent produziu o desenho e o diff inicial, mas nao concluiu seus gates. A
revisao adversarial independente encontrou clock antes do lock, prazo arredondado como ja
expirado, ausencia de versao de schema, overflow de lease e testes de crash falsamente
cooperativos. A aceitacao ocorreu somente depois das correcoes e reexecucao principal.

## Gate

| Checagem | Resultado |
|---|---|
| H10b isolado | `12 passed` |
| H10b + H10a + Caixa + Servico | `52 passed` |
| Suite rastreada, sem packs futuros | `465 passed` |
| Pack completo como overlay | `68 passed, 43 failed` |
| Ruff | limpo |
| mypy | limpo, 71 arquivos |
| Bandit high/high | limpo |
| compileall | limpo |
| Gitleaks dir (`motor/`) | limpo, 16.45 MB |
| build sdist/wheel | passou |
| install e smoke do wheel isolado | passou; registro e claim v1 |

O overlay nao caiu porque H10b nao possuia reprodutor proprio e nao foi ligado ao fluxo de
resume. Os cinco casos G/H11 continuam vermelhos, como esperado. Esta verificacao nao
declara o Gate CI global aprovado nem o motor pronto para producao.

## Security DoD

- SQL: todos os valores externos usam parametros; SQL dinamico contem somente constantes
  internas.
- Input: IDs, texto, duracao, clock e inteiros de lease possuem dominio/tamanho fechados.
- Durabilidade: WAL, FULL e foreign keys sao verificados; falha de capacidade interrompe a
  inicializacao.
- Concorrencia: escritores usam `BEGIN IMMEDIATE`; claim e CAS sao statements atomicos.
- Crash: processo e morto dentro da transacao e a reabertura prova rollback e
  `integrity_check=ok`.
- Segredos/SAST: Gitleaks e Bandit high/high limpos.

No snapshot H10b o arquivo normativo ainda nao existia, por isso esta verificacao aplicou
as regras do AGENTS. H13 restaurou o checklist em `motor/docs/security-DoD.md` e o ponteiro
de descoberta em `docs/security-DoD.md`.

## Tamanho E Landing

O hardening adversarial elevou H10b para cerca de 460 linhas entre producao e testes. Para
preservar PRs revisaveis, o landing deve ser separado sem mudar o comportamento final:

- H10b1: schema/meta, registro atomico, idempotencia, rollback e crash recovery.
- H10b2: claim concorrente, lease, clock apos lock, CAS e limites numericos.

Cada commit/PR deve carregar seus testes causais correspondentes e manter a suite rastreada
verde; nao pousar o diff como uma unica revisao de 460 linhas.

## Onde isto pode dar errado

- O lease pressupoe workers no mesmo host e relogio de parede coerente. Clock skew ou salto
  de NTP pode antecipar/atrasar expiracao; WAL em NFS/filesystem remoto nao e suportado.
- H10b nao possui ack/publicacao, release, consumer, dedupe no estado ou resume. Crash depois
  de efeito externo e antes do ack ainda pode duplicar entrega; H11 deve ser at-least-once.
- Schema legado falha fechado e exige migracao explicita. Nao ha ferramenta de migracao nesta
  fatia porque nao existia versao H10b publicada.
- Se H11 compartilhar o mesmo arquivo do checkpointer, deve inicializar WAL antes de abrir
  conexoes long-lived e manter `caixa_meta` como namespace independente.
- O build vem de checkout sujo de auditoria; release deve ser reconstruido limpo apos H13.
