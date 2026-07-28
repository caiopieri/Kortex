# Fase C — correções dos achados 🔴 (cadeado Anthropic)

> Registro por achado: o que foi corrigido, por que a decisão de design foi essa, e o que
> mudou de contrato. Achados e ordem em [ACHADOS-UNIFICADOS.md](ACHADOS-UNIFICADOS.md).
> Cada item exige, pelo charter: teste que falha → fix → gate → revisão do vendor oposto.
> **A revisão do vendor oposto (GPT-5/Codex) ainda NÃO foi feita para nenhum destes.**

## U-08 — `rodar_com_caixa` nunca renovava o lease (F1)

`claim` declarava `lease_s=30`; as duas chamadas de `ledger.consumir` omitiam `lease_s`, e a
thread de renovação só sobe quando ele é declarado no consumo. Retomada mais longa que a janela
aplicava o efeito e falhava no ACK → linha da outbox reelegível, dois consumers no mesmo job.

**Fix:** constante `_LEASE_CLI_S` usada nos quatro pontos (`caixa.py`), em vez de literal
repetido. O literal era a causa raiz: permitia que claim e consumo discordassem em silêncio.

**Trava estrutural:** `test_claim_e_consumo_da_cli_declaram_o_mesmo_lease` falha se alguém
reintroduzir literal solto ou esquecer `lease_s` no consumo.

**Nota sobre o reprodutor:** a versão original usava relógio falso saltando 120 s. Não podia
passar nem com o fix — a thread de renovação dorme em tempo real, então um relógio que salta
torna a renovação impossível por construção. Reescrito com relógio real e lease encurtado
(`monkeypatch` de `_LEASE_CLI_S` para 0.3 s, retomada de 0.6 s).

## U-01 — gate humano vazava entre jobs (F2)

A nota era `PENDENTE — {portao}.md`, sem o job, e `_decisao_arquivada` fazia glob global no
vault compartilhado. A aprovação dada para o job A era consumida pelo job B, sem interação
humana. Só no caminho CLI (`--caixa`); o serviço responde gates por API.

**Fix:** `CaixaFundador.para_job(job_id)` devolve uma Caixa vinculada; nota e arquivo passam a
`PENDENTE — {job} — {portao}.md` / `decidida … — {job} — {portao}.md`. `rodar_com_caixa` vincula
a Caixa ao `thread_id` antes de tocar em qualquer nota. Componentes do nome passam por
`_validar_componente` (sem separador, sem NUL, sem `.`/`..`).

**Não houve fallback para o nome antigo, de propósito.** Um fallback "se não achar a nota
escopada, procure a global" reintroduz exatamente o vazamento: é esse glob global que o job B
usava para herdar a decisão do job A.

### Mudança de contrato — corpus congelado regerado

Três reprodutores do corpus H11 (`tests/test_auditoria_gpt5_g.py`) respondiam a nota pelo nome
não escopado e passaram a falhar. Eles **não asseveram o nome da nota** — asseveram idempotência
de resume, preservação de decisão pós-crash e dois interrupts concorrentes; a nota é só o
harness. O harness foi adaptado (`.para_job(<thread_id>)`), as asserções ficaram intactas.

| item | antes | depois |
|---|---|---|
| tar | `reproducer-corpus-0bdbb677dd281edc.tar` | `reproducer-corpus-784c478a054ca380.tar` |
| `file_sha256` de `tests/test_auditoria_gpt5_g.py` | `4352…`* | `8c2d39210122ffc0596d80abb2e5f4b5651d49fa58a4b82170b2ae63cba670e6` |

\* ver histórico do `reproducer-manifest.jsonl`. `tests/audit_corpus.py:CORPUS` aponta para o
novo nome. Os 14 casos do arquivo passam contra o motor atual.

> **Isto é a exceção, não a regra.** Editar corpus congelado para fazer teste passar é o
> caminho curto para um gate que não mede nada. Só se justifica aqui porque a mudança de
> contrato foi deliberada, o que o reprodutor mede não mudou, e o registro está nesta tabela.

## U-02 — spec do usuário escapava do teto de custo (S4/S5)

A confrontação com `teto_bootstrap` existia só no ramo gerado pelo planner. Spec vinda da
CLI/serviço — o entrypoint de produção — validava e seguia com `teto_custo` sem limite superior.
É a única contenção monetária do sistema.

**Decisão de design: recusa, não rebaixamento.** O `ACHADOS-UNIFICADOS` deixou em aberto se "a
spec do usuário é soberana" seria intencional. Não é: um teto contornável por quem escreve o
arquivo de spec — o caminho normal — não é teto. Entre recusar e rebaixar em silêncio, recusar
é consistente com o ramo do planner e falha legível na hora, em vez de estourar orçamento no
meio da missão com uma mensagem que não explica por quê.

**Fix:** mesma confrontação no ramo da spec fornecida (`grafo.py`), com a mensagem citando os
dois valores.

**Reprodutor:** `test_A2_spec_do_usuario_pode_elevar_teto_acima_do_bootstrap` media o mecanismo
(exigia que a sessão abrisse, com teto rebaixado). Passou a medir o invariante — *nenhuma sessão
de orçamento abre acima do bootstrap* — que recusa e rebaixamento satisfazem igualmente.

## U-05 — reconciliação descartava o nó culpado (G2)

Havendo reprovado, o veredito era **reconstruído do zero** (`{"aprovado": False, "lacunas": …}`)
e a linha seguinte lia `nos_a_refazer` desse dict mutilado. Com A→B→C, C reprovado e o evaluator
apontando A como origem, a atribuição a montante sumia e a reconciliação refazia só o sintoma C
— queimando uma rodada do teto para corrigir o nó errado. Achado por **dois auditores
independentes** (A1 do kernel e B1 do grafo), o sinal mais forte do lote.

**Fix:** `{**veredito, "aprovado": False, "lacunas": …}` em vez de dict novo. Uma linha. O
fecho transitivo a jusante (`preencher_lacunas`) já existia e estava correto — com `nos_a_refazer`
preservado, `{A}` ∪ `{C}` fecha em `{A, B, C}` sozinho.

## U-03 — falha parcial derrubava o motor (G4/C1)

Tudo depois do veredito do verifier estava fora de guarda. Três caminhos, todos alcançáveis por
spec gerada pelo planner (LLM), já que `produz_artefatos` é `list[dict[str, Any]]` e a validação
não protege:

| entrada | exceção | antes |
|---|---|---|
| `produz_artefatos: [{}]` | `KeyError: 'nome'` | queda do run, sem evento |
| `nome: "sub/dir/x.md"` | `OSError` no `mkdir` | queda do run, sem evento |
| runner que levanta / `\x00` numa entrada | `RuntimeError` / `ValueError` | atravessava a fronteira |

**Fix:** bloco de artefato sob `try` → `portao.reprovado` + resultado reprovado com motivo;
`command_runner.run` sob `try` → `{"ok": False, "erro": "runner_falhou", …}`.

**Por que `except Exception` largo na fronteira do runner:** o `CommandRunner` é um adapter
externo e o protocolo não é validado em runtime — enumerar as exceções de todos os backends
possíveis é justamente o que não dá para fazer. `BaseException` continua propagando
(`KeyboardInterrupt`/`SystemExit` não viram reprovação).

## Ainda abertos

🔴 U-04, U-06, U-07 — os três do curador, que bloqueiam o flywheel. 🟡 os 15, dos quais três
seguem vermelhos por design em
`test_auditoria_anthropic_eventos_caixa.py` (E-01 sidecar, E-02 quarentena, E-03 guard
anti-drift).

### Onde isto pode dar errado

- **U-01 muda o nome de notas que já existem no vault do Caio.** Nota `PENDENTE — <portao>.md`
  escrita antes deste commit fica órfã: o motor não a encontra mais e vai abrir uma nova. Não
  há migração automática — se houver nota pendente real, ela precisa ser renomeada à mão para
  `PENDENTE — <job> — <portao>.md`.
- **O corpus regenerado enfraquece o argumento de "evidência congelada".** A partir de agora o
  tar tem uma edição feita pelo mesmo agente que fez o fix. A mitigação é este registro e a
  releitura pelo vendor oposto — que ainda não aconteceu.
- **U-02 pode quebrar runbook existente.** Qualquer spec de exemplo com `teto_custo` acima do
  `teto_bootstrap_brl` configurado passa a ser recusada no arranque. Não auditei os 25 exemplos
  contra os tetos configurados.
- **U-03 troca queda por reprovação silenciosa.** Antes, spec com artefato malformado explodia
  alto; agora o subagente reprova com motivo e o run segue para reconciliação — que pode gastar
  rodadas do teto tentando refazer um nó cuja spec está errada e vai falhar igual. Isso é
  disponibilidade comprada com custo, e não medi o custo.
- **`except Exception` na fronteira do runner pode mascarar bug do motor**, não só do adapter.
  Uma falha de programação dentro de `CommandRequest` viraria "runner falhou" com o traceback
  perdido na mensagem. O motivo carrega `type(ex).__name__`, mas não o traceback.
- **Nenhum destes cinco foi revisto pelo cadeado GPT-5/Codex**, que é requisito do critério 3 do
  charter. Continuam correções auto-avaliadas.
