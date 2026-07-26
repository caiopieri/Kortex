# ACHADOS — auditoria Anthropic · grupo E (eventos) e grupo A (fundador/caixa)

Escopo: `motor/eventos.py`, `motor/eventos_schema.py`, `motor/caixa.py`, lidos na
íntegra, contra E1, E2 e F1/F2/F3 de `docs/INVARIANTES.md`.

Baseline: `972 passed, 7 skipped` (`.venv/bin/python3 -m pytest -q -p no:randomly`).
**A suíte verde não prova os invariantes** — os dois achados 🔴 abaixo estão em
caminhos que a suíte simplesmente não exercita.

Reprodutores: `tests/test_auditoria_anthropic_eventos_caixa.py` — **vermelho por
design**, 5 testes, todos falham hoje. Nenhum arquivo de produção foi tocado.

| Sev | ID | Área | Uma linha |
|---|---|---|---|
| 🔴 | A-01 | Caixa | Decisão humana de um job é reaplicada silenciosamente em outro job |
| 🔴 | A-02 | Caixa | `rodar_com_caixa` nunca renova o lease: retomada > 30 s aplica o efeito e falha no ACK |
| 🟡 | E-01 | Eventos | Sidecar de lock removido ⇒ dois writers no mesmo inode, `seq` duplicada |
| 🟡 | E-02 | Eventos | Corrupção de linha completa (não-tail) inutiliza o log para sempre, sem quarentena |
| 🟡 | E-03 | Eventos | Guard anti-drift de E1 é cego a emissão com tipo não literal e só varre `motor/*.py` |
| 🟡 | A-03 | Caixa | Testes de concorrência do H11 medem resultado, não exclusão sob corrida real |
| 🟢 | E-04 | Eventos | `LogEventos(truncar=...)` é parâmetro morto; `servico.py` passa `truncar=True` e é ignorado |
| 🟢 | A-04 | Caixa | `owner_id = f"runner-{id(caixa):x}"` não é identidade durável nem única |
| 🟢 | E-05 | Eventos | `status()` do serviço abre um **writer** no log de um job possivelmente vivo |

---

## 🔴 A-01 — decisão de um job é reaproveitada por outro job (viola F2)

**Evidência:** `motor/caixa.py:475`, `motor/caixa.py:605-611`, `motor/caixa.py:663-707`.

A nota do fundador não é namespaced: `_nota_path` → `PENDENTE — {portao}.md`
(`caixa.py:475`), e `_decisao_arquivada` faz glob global
`decidida * — {portao}.md` no diretório da caixa (`caixa.py:607`). O único veto
para reusar uma decisão arquivada é `ledger.tem_historico(job_id=job_id, portao=portao)`
(`caixa.py:676`) — **escopado por job**, enquanto o repositório de notas é global.
E `--caixa <dir>` é, por construção, um vault compartilhado entre runs
(`motor/__main__.py:111-137, 291`); `dir_caixa` exige `run_id` explícito
justamente porque um mesmo diretório serve vários jobs.

Consequência: job-b, num gate do mesmo `portao`, colhe a decisão que o humano deu
para job-a — sem interação humana nenhuma, sem esperar, sem timeout. O gate humano
deixa de ser um gate. Vale também para o caso concorrente: dois jobs vivos no mesmo
`portao` compartilham fisicamente a mesma nota `PENDENTE`, e o primeiro a ler
consome a resposta do outro (`escrever_nota` detecta `path.exists()` e emite
`decisao.retomada` sobre a nota alheia, `caixa.py:525-528`).

**Teste que falha:**
`tests/test_auditoria_anthropic_eventos_caixa.py::test_decisao_de_um_job_nao_pode_ser_reusada_por_outro_job`
→ `Failed: DID NOT RAISE RuntimeError` (job-b conclui com `gate:abortar`, a
decisão de job-a).

Escopo: caminho CLI (`rodar_com_caixa`). `GerenciadorJobs` responde gates por API
(`responder_gate`) e não passa por notas, então o serviço não é afetado.

## 🔴 A-02 — `rodar_com_caixa` não renova o lease (viola F1)

**Evidência:** `motor/caixa.py:643-647` e `motor/caixa.py:711-715`.

Ambas as chamadas são `ledger.consumir(claim, aplicar, fault=fault)` — **sem
`lease_s`**. Em `consumir` (`caixa.py:366-393`) a thread de renovação só sobe se
`lease_s is not None`. O lease é fixo em 30 s (`caixa.py:643`, `caixa.py:712`) e
`aplicar` é `grafo.invoke(...)`: uma retomada real, com chamadas de modelo,
estoura 30 s trivialmente.

Sequência resultante: o grafo é retomado e **o efeito é aplicado**; ao voltar, o
`ack` (`caixa.py:302-313`, cláusula `lease_ate > ?`) falha com
`ValueError: transição de lease inválida`; a linha da outbox fica não-ACKed com
lease expirado. Logo: (a) a CLI aborta com erro apesar do trabalho ter sido feito;
(b) a mensagem volta a ser elegível e é redelivered no próximo start; (c) qualquer
consumer concorrente sobre o mesmo `ledger.sqlite` (o reconciliador de
`servico.py`) pode reclamar o lease expirado e aplicar em paralelo — dois writers
sobre o mesmo job, exatamente o que F1 promete impedir.

A maquinaria de renovação existe e funciona — só o chamador CLI não a usa.
`test_servico.py:373::test_retomada_longa_renova_claim_sem_segundo_writer`, citado
em F1 como prova, exercita **apenas** `GerenciadorJobs` (que passa
`lease_s=self._outbox_lease_s`, `servico.py:486-490`). Nenhum teste cobre a CLI.

**Teste que falha:**
`tests/test_auditoria_anthropic_eventos_caixa.py::test_retomada_longa_pela_cli_renova_o_lease`
→ `ValueError: transição de lease inválida` em `motor/caixa.py:312`, com o estado
do grafo já em `['gate:prosseguir']`.

## 🟡 E-01 — remoção do sidecar de lock dá split-brain de writer

**Evidência:** `motor/eventos.py:95-108` vs. `motor/eventos.py:211-220`.

O log é revalidado a **cada escrita** por `_validar_path_aberto` (inode, nlink,
regularidade). O sidecar `.{nome}.lock` é validado **só na abertura** e nunca mais.
Removido o sidecar, um segundo `LogEventos` cria um novo arquivo de lock, obtém
`flock` sem contenda e escreve no mesmo inode do log:

```
{"t": 0.0,   "seq": 1, "evento": "tarefa.concluida", "missao": "A1"}
{"t": 0.0,   "seq": 2, "evento": "tarefa.concluida", "missao": "B1"}
{"t": 0.001, "seq": 2, "evento": "tarefa.concluida", "missao": "A2"}   <- seq 2 duplicada
```

A docstring de `LogEventos` (`eventos.py:89`) declara "pressupõem um diretorio pai
confiavel", o que cobre o adversário — mas não cobre o cenário operacional banal
(rotação de log, `rm .*` de limpeza, sync de vault). A assimetria é o problema: o
log é defendido contra troca, o lock não. Custo do fecho é baixo (guardar
`(st_dev, st_ino)` do lock e revalidar junto com o log).

Verifiquei e **descartei** os outros vetores de aliasing: caminho relativo vs.
absoluto e diretório symlinkado resolvem para o mesmo inode do sidecar e são
corretamente bloqueados; hardlink e symlink no lock/log são recusados
(`_abrir_regular_sem_links`); `subprocess` roda com `close_fds=True` e os fds têm
`O_CLOEXEC`, então não há herança de lock. Não há `fork` no `motor/`.

**Teste que falha:** `::test_remocao_do_sidecar_nao_pode_permitir_segundo_writer`.

## 🟡 E-02 — corrupção fora do tail inutiliza o log permanentemente

**Evidência:** `motor/eventos.py:142-181`.

`_estado_persistido` define tail como "bytes após o último `\n`" e só isso vai
para quarentena (`eventos.py:176-179`). Qualquer linha **completa** inválida no
prefixo levanta `ValueError` no `__init__` (`eventos.py:155/157/159/161/163/172`)
— e como o construtor é o único caminho de abertura, o run perde para sempre a
capacidade de emitir eventos, sem nada ser quarentenado e sem diagnóstico
estruturado. Não é só ataque: zero-fill pós-crash (ext4 delayed alloc) e edição
manual do vault produzem exatamente isso. E2 promete "recovery de tail com
quarentena"; o comportamento em corrupção de meio de arquivo não está declarado
em lugar nenhum. Fail-closed é defensável; fail-closed-para-sempre-sem-artefato
não é.

**Teste que falha:** `::test_corrupcao_no_meio_do_log_deveria_ser_quarentenada`
→ `ValueError: linha 2 invalida no log`.

## 🟡 E-03 — o guard anti-drift de E1 é mais fraco do que E1 afirma

**Evidência:** `tests/test_eventos_schema.py:10-31, 42-55`.

Três cegueiras:

1. **Tipo não literal.** `_tipos_emitidos_em_codigo` só coleta quando
   `node.args[0]` é `ast.Constant` (`test_eventos_schema.py:22`). `motor/modelos.py:216`
   (`self.log.evento(tipo, **dados)`) é invisível ao guard. Hoje seus chamadores
   são literais, então não há drift real — mas o fecho é acidental, não enforçado.
2. **Superfície.** `RAIZ_MOTOR.glob("*.py")` cobre só `motor/motor/*.py`.
   `scripts/experimento_especialista.py:61` emite `modelo.uso` fora do guard, e a
   lista de tipos monetários vive duplicada num `CHECK` SQL
   (`motor/orcamento.py:607`) que o guard não lê — adicionar um tipo lá sem
   registrá-lo no `ESQUEMA` passa o CI e só explode em runtime no relay.
3. **Só o nome, não os campos.** O guard compara conjuntos de tipos; a
   conformidade de *campos* só é checada em runtime por `valido()`
   (`eventos.py:258`), i.e. o drift vira `ValueError` no meio de um run.
4. `test_guarda_anti_drift_falharia_com_evento_nao_declarado` testa o helper
   contra uma string sintética — prova que o helper funciona no caso feliz, não
   que a superfície real de emissão está coberta. É auto-teste, não invariante.

**Bom resultado a registrar:** escrevi um verificador AST estático de *campos*
(tipo + kwargs vs. `ESQUEMA`/`CAMPOS_OPCIONAIS`) e passei em todos os call sites
literais de `motor/*.py`: **zero drift**. E1 se mantém de fato hoje; é a garantia
que é fraca, não o estado atual. Recomendo promover esse verificador a teste.

**Teste que falha:** `::test_guard_anti_drift_enxerga_emissao_com_tipo_nao_literal`.

## 🟡 A-03 — testes de concorrência que serializam na prática

`tests/test_hardening_h11.py:380::test_claim_vivo_concede_um_unico_consumer` usa
`threading.Barrier(2)` e depois `claim`; `BEGIN IMMEDIATE` serializa os writers e
o encontro na barreira não garante sobreposição na janela crítica. A asserção
(`sum(...) == 1`) é a certa, mas um TOCTOU no `claim` se manifestaria como
*flakiness rara*, não como vermelho. Mesma observação para
`test_claim_serializa_mesmo_job_e_mantem_jobs_distintos_paralelos:419`, que é
inteiramente sequencial (dois handles, chamadas alternadas) apesar do nome.

Contraexemplo positivo, para calibrar: `test_hardening_h07c.py::test_writer_serializa_emissoes_concorrentes_e_reabre`
**prova algo** — 8 threads × 20 eventos com `fsync` (que solta a GIL) dentro da
região crítica; sem o mutex a asserção `seq == range(1,161)` quebra de forma
determinística na prática.

Recomendação: para o `claim`, um teste com N≫2 workers em loop de contenda sobre a
mesma `decisao_id`, afirmando "exatamente um APPLIED e exatamente um efeito", roda
em ms e cobre a janela de verdade.

## 🟢 E-04 — `truncar` é parâmetro morto

`motor/eventos.py:91` aceita `truncar` e `eventos.py:110` documenta que "o writer
v2 sempre abre em append". `motor/servico.py:700-705` chama
`LogEventos(..., truncar=truncar)` com `truncar=True` no caminho de escrita. O
comportamento append é o correto para v2; o parâmetro mentindo na assinatura é que
convida a bug futuro. Remover ou fazer `truncar=True` levantar.

## 🟢 A-04 — `owner_id` derivado de `id()`

`motor/caixa.py:631`: `owner_id = f"runner-{id(caixa):x}"` — endereço de memória,
reutilizado após GC e colidente entre processos. Não explorei violação concreta
(o `NOT EXISTS` do `claim` bloqueia qualquer lease vivo independentemente do
owner, `caixa.py:246-253`), mas a identidade do lease é a única coisa que separa
"eu sou o dono" de "outro processo é o dono" no CAS de `ack`/`renovar_claim`.
`servico.py:297` já usa `uuid.uuid4().hex`; a CLI deveria fazer o mesmo.

## 🟢 E-05 — leitura de status abre writer

`motor/servico.py:612`: `_status_duravel` faz
`LogEventos(self._caminho_log(job_id), truncar=False)` para drenar o relay. Isso
toma o `flock` exclusivo. Num deployment multi-processo (a razão de existir da
outbox durável), `status()` no processo B contra um job vivo no processo A
levanta `RuntimeError: log de eventos ja possui writer ativo` — um caminho de
leitura falhando por causa do writer único. Consistente com a dívida #2 de
`INVARIANTES.md` (recovery exige polling/mesmo `run_id`), mas vale registrar.

---

## Áreas onde NÃO encontrei nada ≥ média

- **`eventos_schema.valido` / domínio monetário** (`eventos_schema.py:479-592`):
  sólido. Cross-field checado com `Decimal` em contexto de precisão explícita
  (`_soma_exata`/`_subtracao_exata`), `bool` rejeitado como `int`
  (`_tipo_valido:445-447`), NaN/Infinity barrados na leitura
  (`parse_constant=_constante_json_invalida`) e na escrita (`allow_nan=False`),
  payload fechado por `payload <= campos`, `event_id` restrito a hex64. Sem
  achado.
- **Idempotência do relay por `event_id`** (`eventos.py:228-252`, `orcamento.py:673-691`):
  correta. A impressão idempotente exclui só `t`/`seq` e inclui `evento`, e é
  calculada do mesmo jeito na recuperação (`eventos.py:168`) e na entrega
  (`eventos.py:239`); divergência levanta antes de escrever e antes do
  `confirmar_pendente`. `publicar_orcamento` rejeita subclasses de `dict`
  (`type(payload) is not dict`) e campos reservados. Sem achado.
- **Defesa contra troca/link do arquivo de log**: `_abrir_regular_sem_links`
  (retry x3, `O_NOFOLLOW`, `O_EXCL`, checagem tripla `lstat`/`fstat`/`nlink`) e
  `_validar_path_aberto` por escrita cobrem replace, unlink e hardlink pós-abertura;
  todos os caminhos de erro fecham os descritores e liberam o lock
  (`_fechar_descritores`). Testado e não quebrado. Só o sidecar ficou de fora (E-01).
- **`seq` contígua e tempo não regressivo**: `_estado_persistido` valida ambos na
  recuperação; `_tempo_atual` usa `time.monotonic` com clamp em `_ultimo_t`. Sem
  achado.
- **`LedgerCaixa` — durabilidade e protocolo CAS**: WAL + `synchronous=FULL`
  verificados por leitura de PRAGMA com falha fechada; versão de schema com veto
  a schema legado; `BEGIN IMMEDIATE` em toda mutação; `claim`/`renovar_claim`/`ack`
  todos com CAS sobre `(outbox_id, lease_owner, lease_version, lease_ate > agora)`;
  serialização por job via `NOT EXISTS`; `_validar_claim_para_entrega` reconfere o
  claim contra o persistido campo a campo antes do efeito. O protocolo em si é o
  ponto mais forte que li nesta fatia — o problema (A-02) é o chamador, não o
  protocolo.

## Onde isto pode dar errado

- **A-01 pode ser considerado "por design"** por quem escreveu o fallback
  `_decisao_arquivada`: ele existe para o crash entre "humano decidiu/nota
  arquivada" e "ledger registrou". Se a resposta for "só rode um job por
  `--caixa`", então o achado vira requisito de operação não documentado — mas aí a
  linha F2 "continuam independentes entre jobs" está errada e precisa ser
  reescrita. Namespear a nota por `job_id`/`decision_id` fecha os dois casos sem
  perder o crash-recovery.
- **A-02 depende de o `ack` ser realmente atingível fora da janela.** Meu
  reprodutor injeta um relógio falso; num deployment onde toda retomada termine em
  < 30 s o defeito nunca aparece. Não meço aqui a distribuição real de latência de
  retomada — mas 30 s fixos para uma retomada que inclui chamadas de modelo é uma
  aposta ruim, e a correção (passar `lease_s=30` nas duas chamadas de `consumir`)
  é de uma linha cada.
- **E-01 fica dentro do modelo de ameaça declarado** ("diretório pai confiável").
  Se o dono aceitar esse pressuposto, o achado cai para 🟢. Reportei 🟡 porque o
  código já gasta esforço considerável defendendo o log do mesmo diretório.
- **Não auditei** `orcamento.py`, `servico.py`, `politica.py`, `curador.py` nem o
  painel além do necessário para rastrear as fronteiras acima — E-05 e a nota
  sobre o `CHECK` SQL em E-03 são observações de passagem, não uma auditoria
  dessas superfícies.
- **Não testei em Linux**, só macOS (Darwin 25.5). Semântica de `flock` sobre APFS
  vs. ext4/NFS pode divergir; sobre NFS `flock` pode degradar para no-op, o que
  tornaria E-01 irrelevante diante de um buraco maior. Vale um probe no ambiente
  de produção real.
