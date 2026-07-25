# HANDOFF CODEX — Esquema de eventos motor→superfície (2 PRs) — ROADMAP Next #5

## Por quê (ROADMAP: "desenhar agora é de graça; retrofitar depois é caro")
O motor já é event-sourced (LogEventos → JSONL, ~32 tipos), MAS os eventos são ad-hoc: nomes/campos não
estão especificados em lugar nenhum. Uma interface viva (Flint, Later) construída contra eventos ad-hoc
quebra a cada rename. O que é CARO retrofitar é o CONTRATO. Então congelamos agora: um esquema TIPADO e
versionado + um canal de stream pela superfície (MCP). A UI em si é Later — isto é só o gancho.

NÃO é UI. É o contrato + o canal. Fazer os 2 PRs na ordem, cada um seu commit + testes. Aditivo, read-only
sobre a execução (não muda orquestração).

## Estado atual (não reinventar)
- `motor/eventos.py::LogEventos.evento(tipo, **dados)` grava `{"t": s_rel, "evento": tipo, ...}`.
- Tipos já emitidos (inventário): executor.chamado/respondeu/erro/escalado, modelo.pin/roteado_tier/
  roteado_capacidade/roteado_ferramentas/falha/fallback/reroteado_esgotado/uso, provedor.auto_esgotado/
  esgotado, portao.aprovado/reprovado, gate.auto, escalado, decisao.{fundador,plano,pendente,retomada,
  timeout}, spec.criada/recebida, paralelo.iniciado/concluido, onda.iniciada/concluida, grafo_dep.iniciado/
  travado, reconciliacao.iniciada/concluida/esgotada, lacuna.preenchida, ferramenta.executada/indisponivel/
  saida_invalida, registro.sem_executor, rota.escolhida, tarefa.concluida/abortada. (Confirmar a lista real
  com `grep -rhoE 'log\.evento\("[^"]+"' motor/*.py | sort -u` antes de escrever o esquema.)
- `motor/mcp_servidor.py` expõe tools de job: despachar_missao, status_missao, responder_gate,
  resumo_missao. NÃO há stream de eventos.

## PR 1 — contrato tipado + guarda anti-drift (motor/eventos_schema.py + tests)
Criar `motor/eventos_schema.py`:
- `SCHEMA_VERSAO = 1`.
- `ESQUEMA: dict[str, dict]` mapeando CADA tipo de evento → `{"categoria": <str>, "campos": [<str>...],
  "descricao": <str>}`. Categorias orientadas à superfície: `ciclo` (agente iniciou/respondeu/erro),
  `fluxo` (ondas, paralelo, arestas), `gate` (portao/gate.auto/decisao), `modelo` (roteamento/uso/falha),
  `resiliencia` (esgotado/reroteado/fallback/escalado), `reconciliacao`, `ferramenta`, `artefato`,
  `missao` (spec/tarefa/rota). Incluir TODOS os tipos já emitidos + os 3 da superfície do PR2
  (`aresta.fluxo`, `custo.tick`, `artefato.atualizou`).
- Helper `valido(evento: dict) -> bool` / `tipos() -> set[str]` p/ consumo por testes e superfície.
- (Opcional, se simples) função `categoria_de(tipo) -> str`.

Teste GUARDA ANTI-DRIFT (o valor central): varrer `motor/*.py` por `log.evento("<tipo>"` e assertar que
TODO tipo emitido está em `ESQUEMA`. Assim o contrato nunca silenciosamente diverge do código — quem
adicionar evento novo é forçado a declará-lo. (Implementar lendo os fontes de motor/ com regex, como o
inventário acima.)

### PR1 DoD
- `eventos_schema.ESQUEMA` cobre 100% dos tipos emitidos hoje; `SCHEMA_VERSAO==1`.
- Teste anti-drift passa (todo `log.evento(...)` do código está no esquema) e FALHARIA se um tipo novo não
  declarado fosse introduzido (provar com um caso negativo no próprio teste, via lista simulada).
- Suíte verde (244+); compileall; mypy ok.

## PR 2 — eventos de superfície faltantes + canal de stream MCP (motor/grafo.py + motor/mcp_servidor.py + tests)
### 2a. Emitir os 3 eventos que a interface precisa e ainda não existem
- `artefato.atualizou` — em `registrar_artefato(...)` (subagente/grafo_dep), quando um artefato é
  gravado: `{nome, tipo, subagente, caminho?}`.
- `aresta.fluxo` — na transição entre nós do `executar_grafo_dep` (quando uma onda alimenta a próxima):
  `{de: <id|onda>, para: <id|onda>}` — o que a UI usa pra animar a aresta. Emitir ao iniciar cada nó com
  suas dependências (`{de: dep, para: sid}` para cada dep) é suficiente.
- `custo.tick` — derivar de `modelo.uso`: ao emitir `modelo.uso`, emitir também (ou no lugar, mantendo
  modelo.uso) um `custo.tick {papel, modelo, total_tokens}` — sinal incremental de custo p/ a UI somar ao
  vivo. (Manter modelo.uso pro curador; custo.tick é a visão de superfície. Se preferir, custo.tick pode
  ser só um alias semântico documentado no esquema apontando p/ modelo.uso — decisão do implementador,
  mas o esquema tem que refletir o que de fato é emitido.)
Declarar os 3 no ESQUEMA (PR1 já os inclui).

### 2b. Canal de stream pela superfície (MCP)
Em `mcp_servidor.py`, novo tool `metafabrica.eventos(job_id: str, desde: int = 0) -> dict`:
- Lê o log JSONL daquele job (o GerenciadorJobs já sabe o caminho do run/log — usar a mesma fonte do
  status/resumo), retorna `{"eventos": [...a partir do índice `desde`...], "proximo_offset": <int>,
  "schema_versao": SCHEMA_VERSAO}`.
- Polling incremental: a superfície chama com `desde=proximo_offset` pra pegar só o novo. Read-only.

### PR2 DoD
- Run stub (grafo_dependencias) emite `aresta.fluxo` entre dep→nó e `artefato.atualizou` quando há
  produz_artefatos; `custo.tick` aparece quando há `modelo.uso`.
- `metafabrica.eventos(job_id, desde=N)` retorna os eventos a partir de N + proximo_offset coerente +
  schema_versao; chamada incremental não repete eventos já lidos.
- Teste anti-drift do PR1 continua passando com os novos eventos (já declarados).
- Suíte verde; compileall; mypy ok. READ-ONLY sobre a execução.

## Validação do Caio (depois dos 2 commits) — NÃO é código
1. Rodar uma missão; confirmar no log.jsonl os novos `aresta.fluxo`/`artefato.atualizou`/`custo.tick`.
2. (Opcional) via MCP, chamar `metafabrica.eventos(job_id, desde=0)` e depois com o `proximo_offset` →
   ver o stream incremental. É o gancho que Flint/Jarvis/painel vão consumir.
Ver agora, sem UI nova: o painel/Studio existentes já leem o JSONL.

## DEPOIS (Later, não agora)
Interface viva no Flint: read-only sobre este stream → zoom semântico (macro→micro) → interceptação
(observar/sugerir/parar/assumir) → replay. Ver BRIEFING-CLAUDE-DESIGN-interface-meta-fabrica.md. O
contrato deste handoff é o que a torna barata e estável de construir.
