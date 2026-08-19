# ESTADO — onde o Kortex está agora

> **Este é o documento vivo.** Ele responde uma pergunta só: *em que ponto da construção
> estamos?* Toda sessão de agente começa por aqui, depois de `AGENTS.md`.
>
> **Atualize este arquivo a cada avanço real.** Avanço real = algo que passou por evidência
> (suíte, portão, conformidade), não algo que foi escrito. Se você marcou um `[x]` sem
> conseguir citar a evidência, desmarque.
>
> **Não registre progresso no `AGENTS.md`.** Ele guarda invariantes que quase nunca mudam e
> só aponta para cá. Documento desatualizado mente — e este mente mais rápido que os outros.

**Última verificação:** 2026-08-19 · `main` = `70ed3ab` (mudanças da issue #5 ainda não commitadas)

---

## 1. A frase curta

O Kortex tem **uma célula de produção funcionando com rigor de engenharia** e **não tem a
linha de montagem que encadeia células**. O motor executa *uma* missão, do enunciado ao
artefato provado por execução real. A camada que compõe missões em fases — o Orquestrador —
está desenhada nos documentos e **não existe em código**.

Quem chega agora: leia a §2, escolha uma frente na §4, e confira na §5 o que já é fato
medido antes de assumir qualquer coisa.

---

## 2. O que ler, nesta ordem

| # | Documento | Por quê |
|---|---|---|
| 1 | `AGENTS.md` | invariantes e regras de contribuição. Curto, obrigatório. |
| 2 | **este arquivo** | onde paramos. |
| 3 | `docs/PARECER-ARQUITETO-visao-vs-sistema.md` | a visão fundadora registrada com fidelidade + veredito estrutural. |
| 4 | `docs/DECISAO-ciclo-de-vida-workflow.md` | **canônico** sobre workflow: template vs missão, catálogo, composição entre casas. Se outro doc conflitar neste tema, este vence. |
| 4b | `docs/DECISAO-canvas-e-operacao.md` + `docs/DECISAO-modos-do-produto-e-colapso.md` | a superfície: zonas de rascunho e roteiro, andares, andon; colapso como apresentação e o modo aplicação. |
| 5 | `motor/docs/INVARIANTES.md` | o que o motor promete e não pode quebrar. |
| 6 | `docs/ROADMAP.md` | prioridades Now/Next/Later. |

Depois, conforme a frente: as demais `docs/DECISAO-*.md`, `docs/ARCHITECTURE.md`,
`docs/LEIA-PRIMEIRO.md`, `motor/docs/EVOLUCAO.md` e as specs em `motor/specs/`.

**Cuidado com data.** O parecer da linha 3 é de 2026-07-06 e trata o portão de processo como
não certificado — isso mudou (§3). Documento antigo não é mentira deliberada; é dívida.

---

## 3. Checklists por frente

### A espinha — vetores V1 a V8

`motor/docs/EVOLUCAO.md` define os vetores de evolução do motor e uma **sequência por
dependência, não por importância** (o próprio doc diz isso). O "Estado dos vetores" lá é de
2026-07-03 e já não vale para o V8. Posição atual:

| vetor | o que é | estado |
|---|---|---|
| **V1** | nós validadores determinísticos como primitiva da spec | **feito** |
| **V2** | contrato de evidência + eventos tipados | **feito** |
| **V3** | curador opera a biblioteca de gates (a catraca) | **feito** — observa, propõe, roda em sombra e certifica; aplicar continua sendo intenção sujeita a portão humano |
| **V4** | fronteira fractal: as casas ficam ACIMA do motor | **guarda permanente, não tarefa** — vale em toda decisão ("isso é músculo ou autoridade?") |
| **V5** | WorkflowSpec v0.2: dependências e handoff entre nós | **parcial** — `grafo_dependencias` roda com handoff via `deps_txt`; falta o **contrato tipado de handoff** e a composição entre casas |
| **V6** | fábrica de especialistas (curador que cria modelos) | **Later por decisão** — gated por V1 (grader), V3 fatia 3 e livro-razão de custo. Provar UM especialista antes de generalizar |
| **V7** | ciclo de vida do workflow (catálogo, versão, autoria-como-run, composição) | **decidido, não construído** — falta catálogo versionado, editor visual, marca de run não-certificado e contrato de composição entre casas |
| **V8** | backends de execução plugáveis e capacidade de computação | **feito em 2026-08-18** — era descrito como *"o desbloqueador"*, aquilo que "vem antes de qualquer coisa nova, inclusive de tela" |

**A fronteira é V5 + V7, e as duas convergem no mesmo tijolo:** o contrato tipado que carrega
proveniência entre runs. O V5 chama de "formalizar o contrato tipado de handoff"; o V7 chama de
"contrato de composição entre casas"; o `DECISAO-ciclo-de-vida-workflow.md` §8 chama de trava, e
diz o que acontece sem ele — *"a composição vira prosa solta e reproduz inconsistência um nível
acima"*.

**Não é verdade que tudo depois de um ponto esteja faltando.** V1, V2, V3 e V8 estão feitos; V4
nunca vira tarefa; V6 está deliberadamente adiado. O que falta é um par específico, e ele é
menor do que a lista sugere.

### A. Núcleo do motor — a célula
- [x] `WorkflowSpec` como dado tipado e versionado; grafo fixo interpreta
- [x] dois padrões de topologia certificados: `fan_out_sintese` e `grafo_dependencias`
- [x] verificação adversarial com retry, escalada de tier e reconciliação limitada
- [x] retry **conserta em vez de refazer** — o rascunho anterior entra no prompt com
      "corrija APENAS o que foi apontado" (`motor/grafo.py:1024`)
- [x] ledger de eventos com schema fechado, append durável e projeções read-only
- [x] gate humano fail-closed: com `--auto`, cobertura reprovada **não** é auto-aprovada
- [ ] evidência do portão fica legível no log (hoje `motivo` fica vazio quando aprova — issue #20)
- [ ] `executor.erro` com classe estruturada em vez de texto livre (issue #12)

### B. Portão de processo e sandbox
- [x] `CommandRunner` como `Protocol`; default é **negar** (`DenyCommandRunner`)
- [x] backend Docker implementado, imagem selada por digest, `--network none`
- [x] **conformidade certificada em Linux dedicado** — 34 testes, engine 29.1.3,
      policy `h05b-docker-v1`. Isto remove a ressalva que contaminava toda evidência
      anterior produzida sob Docker Desktop no macOS.
- [x] missão que produz **um programa**, provado por uso real da CLI e não por import
      (`motor/exemplos/cli-tarefas.json`)
- [ ] portão que exija piso de cobertura — hoje suíte magra passa igual à robusta

### C. Contenção monetária
- [x] reserva conservadora antes de qualquer efeito; custo desconhecido reprova fechado
- [x] snapshots de pricing/FX com prazo de validade; vencido bloqueia
- [x] medição monetária pode ser desligada explicitamente (`sem_contencao_monetaria`)
- [ ] **moeda de contenção para rota grátis** (issue #7). Rota sem preço declarado reprova
      fechado, e cadastrar preço zero silenciaria a única contenção que existe. Hoje há
      centenas de rotas grátis disponíveis e invisíveis para o motor.
- [ ] reserva deixa de usar pior caso de 200k tokens (issue #6)

### D. Interface
- [x] painel React servido pelo `painel.py`, event-sourced sobre o ledger
- [x] aba Canvas lendo o ledger real
- [x] despacho real de missão pela interface, incluindo `--sandbox` (`MOTOR_SANDBOX`)
- [ ] **canvas de autoria interativo** — decidido desde sempre (`DECISAO-canvas-e-operacao.md`
      §3: *"o canvas é uma forma de escrever a spec"*), estava atrás do V8 por sequência
      (*"vem antes de qualquer coisa nova, inclusive de tela"*). **O V8 caiu em 2026-08-18**,
      então esta pendência deixou de estar bloqueada. Depende do contrato tipado (§G).
- [ ] colapso visual de fase, com a regra "caixa colapsada nunca é mais verde que o pior nó
      dentro dela" (`DECISAO-modos-do-produto-e-colapso.md` §2)
- [ ] modo aplicação: interface própria sobre roteiro certificado (idem §3)
- [ ] duas telas do mesmo painel desenham grafos diferentes da mesma run (issue #15)
- [ ] `npm ci` quebrado; builds não são reproduzíveis entre máquinas (issue #16)

### E. Curador e flywheel
- [x] observador read-only de perfis de aptidão a partir dos logs
- [x] **run em sombra** com certificação: McNemar, piso de 30 casos held-out, α=0.05,
      selo HMAC na evidência (`motor/curador.py`)
- [x] intenção de promoção **gated** — propõe, nunca muta o catálogo sozinho
- [ ] repositório autoritativo de certificação
- [ ] versionar **templates de workflow** com evidência (hoje o registro cataloga rotas de
      modelo, não templates)

### F. Infra 24/7
- [x] runner Linux dedicado provisionado e provado (ver §5)
- [x] painel servido na LAN por systemd
- [ ] Kortex sobe sozinho no boot — hoje o 24/7 é do hardware, não do serviço
- [ ] OmniRoute deixa de ser ponto único de falha

### G. A fábrica — a camada acima
- [ ] **Orquestrador**: não existe `orquestrador.py`. É a camada que encadeia runs entre
      casas (`DECISAO-ciclo-de-vida-workflow.md` §8, §9)
- [ ] **catálogo de templates** de workflow com metadado "quando usar" (§2)
- [ ] **artefato tipado com proveniência atravessando runs** — a trava explícita do §8.
      Sem ela a composição vira prosa solta. **É o tijolo que destrava os outros.**
- [ ] estado de projeto entre missões — hoje cada run é um `runs/<id>` que esquece tudo
- [ ] quadro/kanban roteando tarefa e feedback do usuário para a etapa certa
- [x] **duas missões em paralelo** (issue #5, P0). A CLI grava cada missão em
      `runs/<run_id>/log.jsonl` sob flock exclusivo; o painel descobre os arquivos e mantém
      o log raiz como legado. O cenário offline com duas missões sem `--caixa` conclui ambas
      e as separa no painel. O mesmo cenário com `--caixa` mediu contenção no `motor.db`
      compartilhado (`sqlite3.OperationalError: database is locked`), registrada na issue #21;
      a separação JSONL está fechada, o checkpointer SQLite não está.
      Linha de produção sem concorrência não é linha.

---

## 4. Se você vai desenvolver agora

**A ordem que o estado atual sugere**, não é ordem imposta:

1. **Issue #5** (paralelo) — P0 declarado, trava a software house.
2. **Artefato tipado com proveniência** (§G) — o tijolo que destrava composição.
3. **Issue #7** (moeda de contenção grátis) — destrava as rotas que já estão disponíveis.

Antes de mexer em qualquer uma, confirme na §5 se o que você presume ainda é verdade.

---

## 5. Fatos medidos — o que é evidência, não impressão

Reproduza antes de citar. Todos abaixo foram verificados em 2026-08-19.

- **Suíte (baseline antes da issue #5):** 1244 passam, 35 pulados, **1 falha (E-02**,
  `test_corrupcao_no_meio_do_log_deveria_ser_quarentenada`, colisão de contrato conhecida e
  aceita). Rode **uma por vez por checkout** — `log.jsonl` abre sob flock exclusivo.
- **Issue #5 medida (2026-08-19):** o teste offline causal cobre duas threads e duas
  `run_id`s. Sem `--caixa`, ambas retornam 0, cada log tem `seq` independente e
  `/dados/runs/<id>` devolve somente os eventos daquela missão. Com `--caixa`, a corrida
  também foi executada; uma medição reproduziu `missao-a: sqlite3.OperationalError('database
  is locked')` e `missao-b: BrokenBarrierError()`. Isso é a dívida #21 do `motor.db`, não
  uma falha do isolamento JSONL.
- **Python:** `requires-python = ">=3.10,<3.14"` está **correto e é portador de carga**. Em
  3.14 o `pydantic.v1` (importado por `langchain_core` na cadeia do `langgraph`) perde campos
  silenciosamente — `class M(B1): x:int; M(x=5).x` levanta `AttributeError` (PEP 649 vs.
  metaclasse v1). Em 3.13 funciona. **Não suba esse teto** (issue #8 está enunciada ao
  contrário: o pyproject está certo, o ambiente é que fica fora).
- **Runner 24/7:** `cap@192.168.15.50`, Ubuntu 26.04, i5-4300M, 7.2 GiB, bare metal.
  Python 3.13.15 via `uv` (a 26.04 só oferece 3.14 no apt). Docker 29.1.3. Suspensão
  neutralizada. Painel em `http://192.168.15.50:8378`.
- **Imagem de sandbox do runner:**
  `kortex/sandbox@sha256:fff5052b0fca1b80089c3951c4564dfc3744b87a9d20c79b171fc4830e461214`
  (amd64/linux), manifesto em `exemplos/sandbox-kortex-linux.json`. Digest é **identidade de
  evidência**: outra máquina, outro digest, outro arquivo — nunca repontar o existente.
- **Modelo listado em `/v1/models` não significa modelo utilizável.** O OmniRoute lista rotas
  sem credencial ativa e só a chamada real revela o 404. Teste a chamada, não o catálogo.
- **Snapshot de rotas grátis vencido** (117h contra limite de 24h). O motor recusa com
  *"adiantar só a data não prova gratuidade nem disponibilidade"*. Disponibilidade (HTTP 200)
  **não** é gratuidade — remedir exige olhar consumo no provedor.

---

## 6. Como manter este arquivo honesto

- Marque `[x]` só com evidência citável. Sem evidência, é `[ ]`.
- Ao fechar um item, mova o fato medido para a §5 com a data.
- Ao descobrir que um documento antigo mente, **diga aqui qual e em quê** — como a §2 faz com
  o parecer. Não reescreva o documento antigo em silêncio.
- Issues vivem em `caiopieri/Kortex-backup` (repo privado; o código é público). Não duplique a
  lista aqui — referencie o número.
