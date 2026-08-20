# HANDOFF CODEX — Interface viva P0 (board de missões · Grafo 2D · Caixa do Fundador · editor mínimo)

> Handoff travado pelo Arquiteto (2026-07-04). Baseado em
> `docs/design/BRIEF-DESIGN-interface-meta-fabrica.md` (spec de design, v2) e
> `docs/DECISAO-ciclo-de-vida-workflow.md` (regras do editor de workflow). Empacota 4 frentes
> encadeadas num handoff só, no molde de `motor/handoffs/HANDOFF-CODEX-item3B-medidor-lift-v3.md`
> (frentes independentes, cada uma podendo virar commit próprio, relato único). Ordem: mais
> barato/read-only → mais arriscado.

## Por quê (amarra à arquitetura)

O painel começou como um mapa orbital de UM log.jsonl fixo; a issue #5 agora entrega a leitura
de múltiplos logs por run. `/` (painel 2D força-dirigida antigo), `/dados` (nós/arestas/eventos derivados do log) e
`/grafo3d` (grafo 3D, ver `motor/handoffs/HANDOFF-CODEX-grafo3d-painel.md`, precedente direto de
como plugar vista nova sobre `/dados` sem tocar o motor). O brief de design (§8.1, §8.2, §8.3a,
§8.5) pede uma interface que **audita** essa telemetria em vez de o Caio operar cru: board de
missões, grafo com drawer, Caixa do Fundador, editor de workflow. Nenhuma dessas telas calcula
nada — elas **renderizam eventos que já existem** em `motor/motor/eventos_schema.py` (48 tipos) e,
na única frente que escreve (F3), devolvem uma decisão pelo mesmo caminho que já existe
(`GerenciadorJobs.responder_gate`, hoje exposto via MCP em `motor/motor/mcp_servidor.py`). P0 é
"cockpit mínimo" (brief §13): não é para inventar dado, é para deixar de olhar JSONL cru.

## Achado que muda o desenho (leia antes das frentes)

O painel atual (`motor_painel/painel.py`) é **multi-run** para o board/endpoints de runs:
`MOTOR_WORKSPACE/<job_id>/log.jsonl` é a fonte principal e o `LOG_PATH` raiz é legado somente
leitura. O motor real roda multi-run — cada missão despachada
por `GerenciadorJobs.iniciar()` grava seu próprio log em `workspace_base/<job_id>/log.jsonl`
(`motor/motor/servico.py:277`, `_log_path`). Board de missões (F1) e Caixa do Fundador (F3) só
fazem sentido **multi-run** (mais de uma missão em estágios diferentes ao mesmo tempo). Isso exige
o painel passar a **escanear um diretório de runs** (`workspace_base/*/log.jsonl`) em vez de um
arquivo único — **decisão aprovada pelo Arquiteto** (aditiva: `/dados` sem parâmetro continua lendo
o `LOG_PATH` de sempre). Ver as quatro decisões travadas na seção final.

---

## Frente F1 — Board de missões (read-only, 100% derivado do log)

Vista nova em `motor_painel/board.html`, servida por nova rota `GET /board` em `painel.py`.

- **Fonte de dado:** cada missão = um diretório `workspace_base/<job_id>/log.jsonl`. Endpoint novo
  `GET /missoes` no `painel.py` que:
  - lista os `job_id` encontrados sob o diretório de runs configurado (novo parâmetro/env, ex.
    `MOTOR_PAINEL_RUNS`, análogo a `MOTOR_WORKSPACE` do `servico.py` — **não reusar o mesmo objeto
    `GerenciadorJobs`**, F1 só lê arquivo, não abre SQLite/checkpointer);
  - para cada `job_id`, roda `parse_eventos()` (já existe, importável) sobre o `log.jsonl` daquele
    diretório e deriva **coluna do board** pelos eventos — sem estado paralelo:
    - `spec.recebida`/`spec.criada` sem mais nada → **Planejamento** (a missão nasceu; ainda não
      há `paralelo.iniciado`/`grafo_dep.iniciado`);
    - `paralelo.iniciado` ou `grafo_dep.iniciado` presente, sem `decisao.pendente` aberta e sem
      `tarefa.concluida`/`tarefa.abortada` → **Produção**;
    - `decisao.pendente` presente e **mais recente** que a última `decisao.fundador`/
      `decisao.retomada` para o mesmo `portao` → **Precisa de você** (âmbar, brief §8.3a coluna 4);
    - `tarefa.concluida` → **Concluída** (verde); `tarefa.abortada` → **Concluída** com bolinha
      vermelha (o board não tem coluna própria de erro — brief §8.3a só define 5 colunas; abortada
      cai em Concluída com status vermelho, §4).
  - **"Ideias" fica vazia sempre em P0** — não existe evento de "ideia crua" no schema hoje
    (`spec.recebida`/`criada` já é missão instanciada, não ideia de backlog). Sem dado fictício:
    a coluna renderiza, mas nunca populada por P0. Isso é um corte, não um bug — anotar no relato.
- **Card do board:** `job_id` (mono, ex. `RUN-...`), `missao` (de `spec.recebida.missao` ou
  `spec.criada.missao`), bolinha+forma do status (§4 do brief), última linha = string do último
  evento (ex. `portao.reprovado: verifier:pesquisa-beta — faltou evidência quantitativa`).
- **Sem dado fictício:** diretório de runs vazio/ausente → todas as colunas vazias, sem exception.
- **Não implementar em F1:** arrastar card, criar missão pelo board, abrir chat do Planejador
  (§8.3a menciona isso para a coluna Planejamento — é escrita, cai fora do escopo read-only desta
  frente; ver corte em PENDENTE DECISÃO).

## Frente F2 — Grafo 2D read-only da run (nós/arestas do padrão `grafo_dependencias`)

Vista nova `motor_painel/grafo2d.html` (ou evoluir a `/` existente — decisão do implementador,
desde que `/` continue respondendo 200 com o que responde hoje) + endpoint que aceita
`?job_id=<id>` para escopar a um run específico (hoje `/dados` só lê o `LOG_PATH` fixo — manter
`/dados` **sem parâmetro** intacto para não quebrar `/grafo3d`, que depende dele; acrescentar
`/dados?job_id=X` como variante aditiva apontando para `workspace_base/<job_id>/log.jsonl`).

- **Reusar `grafo_do_log()`** (`motor_painel/painel.py:79`) como base, mas ele hoje **não conhece**
  vários eventos do schema atual — foi escrito para o vocabulário do v0.5
  (`TIPOS_EVENTO` em `painel.py:41-50`), que não inclui `validador.rodou`, `reconciliacao.*`,
  `onda.*`, `rag.consultado`, `decisao.plano`, `gate.auto`, `run.perfil`. F2 precisa **estender**
  `grafo_do_log()` (sem quebrar os testes existentes de `test_painel.py`) para:
  - `validador.rodou` → nó de tipo **`validador`** (distinto de `portao`/verifier — o brief §6 é
    explícito que verificador LLM e validador determinístico são ícones diferentes); aresta do
    `alvo` para o nó validador; cor por `aprovado` (bool).
  - `onda.iniciada`/`onda.concluida` → agrupar visualmente os `ids` da onda (mínimo: badge/label
    no payload, o styling fica pro HTML).
  - `reconciliacao.iniciada`/`concluida`/`esgotada` → badge nos `nos` afetados (`nos` do payload).
  - Nada disso precisa virar UI rica em P0 — o mínimo é o payload `/dados` carregar esses eventos
    sem erro e o grafo distinguir cor por status (§4: azul executando, verde aprovado, vermelho
    reprovado, âmbar decisão pendente), coerente com o precedente do grafo3d
    (`HANDOFF-CODEX-grafo3d-painel.md`: "cores por tipo real", "aresta viva só com evento recente").
- **Drawer, chat de nó, timeline com filtro (§8.5)** ficam fora de F2 — são MICRO (zoom semântico
  §7.3) e direcionamento ao vivo, que é escrita/interação, não esta frente read-only. Cortar e
  anotar.
- **DoD mecânico:** replicar a sonda do grafo3d — instância isolada do servidor, `log.jsonl`
  fabricado (reusar/estender `motor/exemplos/log-amostra.jsonl` com um `validador.rodou` e uma
  `reconciliacao.iniciada`), HTTP GET, verificar que o nó validador aparece e que cor bate o
  esperado.

## Frente F3 — Caixa do Fundador (a única escrita; reusa `responder_gate`)

Vista nova `motor_painel/caixa.html` + rotas novas:

- `GET /pendencias` — lista, por `job_id` (mesmo escaneamento de diretório de F1), os runs cujo
  **estado atual** é gate pendente. **Não reimplementar a lógica de estado** — reusar
  `GerenciadorJobs.status(job_id)` (`motor/motor/servico.py`), que já devolve
  `{"estado": "gate_pendente", "gate": {...}}` com `gate.portao`/`gate.pergunta`/`gate.opcoes`
  (`_gate_resumo`, `servico.py:295`). Isso significa **F3 precisa instanciar um
  `GerenciadorJobs`** dentro do processo do painel (mesmos parâmetros de env que
  `motor/motor/mcp_servidor.py:_gerenciador_de_env` já usa: `MOTOR_DB`, `MOTOR_WORKSPACE`,
  `MOTOR_MODELOS`/`MOTOR_REGISTRO`) — **não recriar** a classe, importar de `motor.servico`.
- `POST /pendencias/<job_id>/responder` com body `{"decisao": "..."}` → chama
  `jobs.responder_gate(job_id, decisao)` **sem transformação** (é literalmente o mesmo caminho que
  o Jarvis usa via MCP hoje — **não criar segunda lógica de decisão**, decisão pétrea do
  direcionamento). Devolve o retorno cru do método (`{"estado": "em_execucao"}` ou erro).
- **Item da fila (brief §8.2):** origem = `job_id` + `missao`; pergunta = `gate.pergunta`; opções =
  `gate.opcoes`; contexto lado a lado = o `motivo` do último `portao.reprovado` daquele job (se
  houver) lido do próprio `log.jsonl` — **não inventar campo novo**, é grep no log já parseado.
- **Decisão é individual** (brief §8.2) — sem endpoint de lote em P0.
- **Fronteira mantida:** nada de gate de dinheiro/identidade aqui (não existe no motor hoje; não é
  preciso excluir nada, só não inventar).

## Frente F4 (última, mais arriscada) — Editor de workflow MÍNIMO

Escopo **deliberadamente cortado** pelo direcionamento do Arquiteto — não é o editor visual de
grafo completo do brief §8.5 ("modo edição"), é o mínimo que a `DECISAO-ciclo-de-vida-workflow.md`
exige para um rascunho não-certificado existir:

- Vista `motor_painel/editor.html`: carrega um template do catálogo (`motor/exemplos/*.json` —
  reusar os arquivos existentes como "catálogo" de fato, não inventar um registro novo em P0),
  mostra o JSON da `WorkflowSpec` (textarea ou editor JSON simples — **sem** canvas de nós
  arrastáveis; isso é o "editor visual" do brief §8.5, que o próprio brief marca como evolução
  P1/P2 de "hoje a spec se edita como JSON").
- `POST /rascunhos` recebe o JSON editado, **valida contra `WorkflowSpec`**
  (`motor.spec.WorkflowSpec.model_validate`, mesma classe que o motor usa — reusar, não
  reimplementar regras de `padrao`/`fan_out_sintese`/`grafo_dependencias`/validador/gate já
  codificadas em `motor/motor/spec.py`). Se inválida, devolve os erros do pydantic; **não salva**.
- Se válida, **salva como arquivo em `motor/exemplos/rascunhos/<nome>.json`** (diretório dedicado,
  configurável por env) — **não dispara run**. Disparar é `+ Nova missão` (fora de P0).
- **Marca de rascunho (DECIDIDO pelo Arquiteto):** convenção de diretório, sem campo novo na
  `WorkflowSpec` e sem tocar o motor. Tudo que o editor salva vive em `rascunhos/`; a certificação
  continua sendo propriedade do **run** (mecanismo `run.perfil`/`--rascunho`, commit `0959e63`).
  O fio "disparo a partir de `rascunhos/` força `--rascunho` automaticamente" fica explicitamente
  **fora de P0** — anotar como lacuna conhecida no relato, não resolver agora.
- **Trava de topologia (`DECISAO §4`, brief §8.5):** o editor só deixa editar **dentro** dos dois
  padrões certificados (`fan_out_sintese`, `grafo_dependencias`); a validação do pydantic já rejeita
  ciclo/dependência quebrada/validador que se auto-valida/nó sem rubrica (`spec.py:_consistencia`)
  — **reusar esse validador como a única fonte de verdade**, não duplicar regras no HTML/JS.

---

## Restrições pétreas (todas as frentes)

- **Nada no motor core** além de, no máximo, endpoints novos em `motor_painel/painel.py` e imports
  de `motor.servico`/`motor.spec` (leitura/reuso, não reimplementação).
- Rotas existentes `/`, `/dados` (sem parâmetro), `/grafo3d` **intactas** — testar regressão
  (`test_painel.py` já cobre `/dados`/`/`; F2 acrescenta caso para `/grafo3d` continuar 200).
- **Sem dado fictício/mock em produção** — toda vista vazia quando o log/diretório está vazio.
- **Sem framework novo pesado** — seguir o que o painel já usa: HTML autocontido + `fetch`, sem
  build step, sem npm (mesmo padrão do grafo3d: CDN se precisar de lib JS).
- **Inerte por default:** nenhuma frente muda comportamento de rota existente sem novo parâmetro
  explícito (`?job_id=`, rota nova).
- **Higiene git:** `git status` antes de commitar; add específicos por frente; nunca `git add -A`.
- **Suíte verde por frente** — cada F* termina com `pytest` passando antes de ir para a próxima.

## DoD por frente (sonda mecânica — precedente: grafo3d)

Todas seguem o padrão do `HANDOFF-CODEX-grafo3d-painel.md`: subir o servidor numa porta isolada
apontando para um `log.jsonl`/diretório de runs **fabricado no teste** (não o log real), bater
HTTP nas rotas novas, e checar o corpo/JSON — nunca "abrir no navegador e olhar".

1. **F1:** diretório fabricado com 3 sub-runs (`job-a/log.jsonl` só com `spec.recebida`;
   `job-b/log.jsonl` com `paralelo.iniciado` e sem conclusão; `job-c/log.jsonl` com
   `decisao.pendente` sem `decisao.fundador` posterior) → `GET /missoes` devolve os 3 job_ids nas
   colunas Planejamento/Produção/Precisa de você respectivamente; diretório vazio → lista vazia,
   sem exceção; `/board` responde 200.
2. **F2:** `log.jsonl` fabricado com `validador.rodou` (aprovado=false) e `reconciliacao.iniciada`
   → `/dados?job_id=X` inclui o nó validador com o status certo; `/dados` (sem parâmetro) e
   `/grafo3d` continuam 200 e iguais ao comportamento pré-F2 (regressão).
3. **F3:** `GerenciadorJobs` fabricado em teste (SQLite temporário, workspace temporário) com um
   job em `gate_pendente` → `GET /pendencias` lista o job com `pergunta`/`opcoes`; `POST
   /pendencias/<id>/responder` com uma decisão válida → o `status(job_id)` subsequente sai de
   `gate_pendente` (mesmo contrato que `responder_gate` já garante — testar via o próprio
   `GerenciadorJobs`, não reimplementar asserção de estado).
4. **F4:** POST com JSON de `WorkflowSpec` inválido (ex. subagente validador sem `valida`) →
   400/erro com a mensagem do pydantic, nada salvo; POST com spec válida (reusar um dos
   `motor/exemplos/*.json` existentes) → arquivo aparece no destino configurado; nenhuma run
   dispara (checar que nenhum `GerenciadorJobs.iniciar` foi chamado).
5. Todas: `pytest motor/tests/` verde ao final de cada frente; `test_painel.py` sem regressão.

## O que isto prova e o que NÃO prova

**Prova:** que as 4 telas do P0 do brief (§8.1 fila de decisão / §8.3a board / §8.5 grafo / editor
mínimo) podem ser desenhadas **sem inventar dado** — 100% derivadas de eventos já emitidos pelo
motor e de mecanismos de escrita já existentes (`responder_gate`, `WorkflowSpec.model_validate`).
Prova que "board" e "grafo 2D" funcionam sobre múltiplos runs reais, não só o log legado do
painel v0.5. A contenção do checkpointer SQLite quando duas missões usam `--caixa` continua
fora desta entrega e está registrada na issue #21.

**NÃO prova:** não é a interface completa do brief — faltam drawer com chat de nó (MICRO, §7.3),
timeline com filtro por tipo (§8.5), "Ideias" populado (não há evento de backlog cru no schema),
editor visual arrastável (§8.5 "modo edição" completo, P1/P2 por design do próprio brief), Home
(§8.1, com Orquestrador/custos/agentes — nenhuma frente aqui a cobre), autenticação/tema (não
testado), e não prova que o mecanismo de propagação "arquivo de rascunho → run marcado
não-certificado" (F4) está fechado — isso é a lacuna sinalizada abaixo.

---

## DECISÕES TRAVADAS PELO ARQUITETO (2026-07-04 — não relitigar no implemento)

1. **Multi-run APROVADO.** O painel passa a escanear o diretório de runs
   (`workspace_base/<job_id>/log.jsonl`, mesmo layout do `servico.py`), de forma **aditiva**:
   `/dados` sem parâmetro continua lendo o `LOG_PATH` de sempre; `/grafo3d` intacto.
2. **F3 instancia `GerenciadorJobs` no processo do painel — APROVADO** (reuso de classe, caminho
   único de decisão; a alternativa via stdio MCP é cara demais pro ganho). **Trava de concorrência:**
   o SQLite pode estar aberto também pelo processo MCP — tratar `database is locked`/erro de lock
   com resposta HTTP de erro limpa (não corromper, não retry infinito), e anotar no relato que
   painel e MCP respondendo o MESMO gate simultaneamente é cenário sem garantia (aceito em P0).
3. **F4 marca de rascunho = convenção de diretório** (`rascunhos/`), sem campo novo na spec, sem
   tocar o motor. Certificação segue propriedade do run (`run.perfil`). O fio "disparo automático
   com `--rascunho` a partir de `rascunhos/`" fica fora de P0, anotado como lacuna conhecida.
4. **Corte do chat do Planejador CONFIRMADO.** F1 é read-only: a coluna Planejamento mostra a
   missão, não abre chat. Interação viva (chat de nó, co-autoria) é pacote futuro (P1).
