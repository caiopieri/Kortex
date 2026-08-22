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

**Última verificação:** 2026-08-20 · `main` = `e2c85e2`

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
| 2b | `docs/PENDENCIAS-DO-FUNDADOR.md` | o que **só o Caio** resolve. Se você é agente, não espere por nada daqui: pegue outra coisa. |
| 3 | `docs/PARECER-ARQUITETO-visao-vs-sistema.md` | a visão fundadora registrada com fidelidade + veredito estrutural. |
| 4 | `docs/DECISAO-ciclo-de-vida-workflow.md` | **canônico** sobre workflow: template vs missão, catálogo, composição entre casas. Se outro doc conflitar neste tema, este vence. |
| 4b | `docs/DECISAO-canvas-e-operacao.md` + `docs/DECISAO-modos-do-produto-e-colapso.md` | a superfície: zonas de rascunho e roteiro, andares, andon; colapso como apresentação e o modo aplicação. |
| 4c | `docs/DECISAO-harness-e-costura-de-execucao.md` | por que o Kortex **não** constrói harness próprio, e onde a costura impõe os invariantes. Com experimento medido. |
| 4d | `docs/DECISAO-consulta-declarada-e-linha-de-recall.md` | quando um agente pode falar com outro (declarado antes, nunca espontâneo) e o que acontece com artefato já entregue. |
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
- [ ] evidência do portão fica legível no log (hoje `motivo` fica vazio quando aprova)
- [x] falha de rota deixa `modelo.falha` com papel, rota, provedor e classe estruturada
      (`sem_resposta`, `pre_efeito`, `terminal` ou `sem_rota`) — issues #12/#20
- [x] `executor.erro` carrega a classe estruturada da tentativa custeada; ausência de rota
      emite também `registro.sem_executor` sem reutilizar o veredito inválido

### B. Portão de processo e sandbox
- [x] `CommandRunner` como `Protocol`; default é **negar** (`DenyCommandRunner`)
- [x] backend Docker implementado, imagem selada por digest, `--network none`
- [x] **conformidade certificada em Linux dedicado** — 34 testes, engine 29.1.3,
      policy `h05b-docker-v1`. Isto remove a ressalva que contaminava toda evidência
      anterior produzida sob Docker Desktop no macOS.
- [x] missão que produz **um programa**, provado por uso real da CLI e não por import
      (`motor/exemplos/cli-tarefas.json`)
- [ ] portão que exija piso de cobertura — hoje suíte magra passa igual à robusta
- [ ] **executor com ferramenta.** O Kortex NÃO é harness: zero `tool_call` no motor, o
      executor devolve `-> str`. Um subagente não lê arquivo, não roda código, não itera.
      Decidido alugar o laço e ser dono dos invariantes
      (`docs/DECISAO-harness-e-costura-de-execucao.md`), com experimento medido em
      2026-08-19 provando que os três invariantes cabem nos pontos de interceptação do DSH.

### C. Contenção monetária
- [x] reserva conservadora antes de qualquer efeito; custo desconhecido reprova fechado
- [x] snapshots de pricing/FX com prazo de validade; vencido bloqueia
- [x] medição monetária pode ser desligada explicitamente (`sem_contencao_monetaria`)
- [ ] **moeda de contenção para rota grátis** (issue #7). **O `omniroute pricing` NÃO
      serve como "leitor real"** — levantado em 2026-08-19: ele sincroniza de
      `BerriAI/litellm` (`model_prices_and_context_window.json`), é opt-in
      (`PRICING_SYNC_ENABLED` default false), e classifica "grátis" por **tabela** — id
      terminando em `:free`, preço zero declarado, ou catálogo estático
      `FREE_MODEL_BUDGETS`. É outra tabela declarada que pode estar velha ou errada,
      **não é prova de faturamento**. O guarda do motor pede "remeça contra o leitor
      real"; isto não é o leitor real. Rota sem preço declarado reprova
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
- [x] duas telas do mesmo painel desenham grafos diferentes da mesma run (issue #15)
      **Fechado em 2026-08-20:** a projeção canônica de `/dados` agora calcula o grafo
      por run; o Canvas consome `runs[].nos`/`runs[].arestas` e só enriquece estado,
      falhas e artefatos. A medição causal encontrou no diamante A→{B,C}→D: o painel
      antigo produzia 8 nós e 0 arestas de fluxo, enquanto o Canvas produzia 5 nós e
      4 arestas. O contrato compartilhado elimina a reprojeção independente.
- [x] **o painel não fabrica mais dado** (issue #23, 2026-08-20). `CatalogoWorkflows` devolvia
      cinco workflows inventados quando o catálogo vinha vazio, **três marcados
      `certificado`**, com versão, contagem de nós e data. Removido, e a tela renomeada para
      **Rotas do registro**, que é o que ela sempre mostrou — `exemplos/registro/*.md` com
      `tipo: rota`, não templates. Irmãos varridos e corrigidos junto: custo fabricado
      (`"US$ 0.20 – 0.60"`) sob o rótulo *"custo estimado · run"* logo acima da caixa
      "consome créditos" em `NovaMissao`, e o `~7 nós` da mesma tela — a spec despachada
      declara **1** subagente em qualquer rota; duas "ideias" semeadas no `Board`; o nó
      `{id:'planner'}` inventado pelo `Grafo2D` quando o grafo está vazio;
      `versao: "1.0.0"` preenchida pelo `obter_catalogo()` para arquivos que não declaram
      versão; e o bucket `'—'` do `Datahouse` que virava *"Runs produtoras: 1"*. O issue #24
      fechou a proveniência: eventos novos carregam `run_id` no envelope e
      `artefato.atualizou` carrega `hash`; eventos legados continuam aceitos pelo schema.
- [x] **a superfície declara o que o ledger não explica** (issue #22, 2026-08-20). Novo
      `/dados/orfaos` conta o que existe em disco e não tem evento, e o `Datahouse` mostra o
      número. **Não reconstrói**: o órfão aparece como caminho e nada mais — sem run, tipo
      nem data, porque o diretório sugere os três e nenhum foi registrado
- [x] **sete cortes na interface, e o 3D volta como modo de vista** (2026-08-21, merge `db539a1`).
      Saíram cinco telas e dois controles que afirmavam mais do que o ledger diz: `Grafo3D`
      antigo, `Grafo2D` (com o `reactflow`), `MapaGeral` (inventava "projeto" a partir de
      `objetivo`), `Home` (repetia Custos/Runs e **decidia** gates, duplicando a Caixa do
      Fundador — e trazia um "Mapa geral vivo" que era **SVG desenhado à mão** sob rótulo
      *"tempo real"*, o sétimo irmão da #23), `Skills` (recombinação mais pobre de Inventário
      + Agentes), três dos quatro temas, e a pílula *"Projeto: Todos"* com `cursor: default`
      — forma de filtro, sem filtro atrás.
      **Medido por mim, não reportado:** bundle 543 kB / 155.89 kB gzip / 76 pacotes →
      **351.35 kB / 99.99 kB gzip / 26 pacotes**; suíte **1280 passam, 35 pulados, 1 falha
      (E-02)**; `npm test` 58/58.
      O 3D voltou com uma regra: **a onda declarada é o eixo Z (`fz` fixo), a física só
      espalha dentro da onda** — grafo force-directed livre *inventa posição*, que é a mesma
      falta que matou o `MapaGeral`. Topologia idêntica à do 2D, com teste irmão do #15.
      A CDN do unpkg saiu: `three` e `3d-force-graph` agora são dependência, em chunk sob
      demanda de **412.15 kB gzip** que não pesa na abertura.
      **Achado que nenhum portão pegaria:** duas cópias do `three` (o `3d-force-graph` declara
      faixa aberta `>=0.118 <1` e resolve para a mais nova) — instalação limpa, build verde,
      1280 testes verdes, e a tela abrindo **preta**. Só apareceu abrindo a tela. Travado com
      `resolve.dedupe: ['three']`.
      **Ressalva registrada:** o `fz` é testado como *contrato* (está setado, constante por
      onda), não como *resultado* — que o `d3-force-3d` honra `fz` foi verificado por olho.
      Se a biblioteca trocar de motor de física, o teste segue verde e a tela mente.
- [x] `npm ci` **volta a funcionar** (issue #16) — faltavam 23 linhas de `@emnapi/core@1.11.3`
      no `package-lock.json`; `npm install` as regenerou e o `npm ci` passa. Correção
      incidental, não pedida: separar do resto se atrapalhar a revisão

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
- [x] **painel servido na LAN por systemd** — verdade desde 2026-08-21, e **antes disso esta
      linha estava errada**. Medido em 21/08: o painel rodava como processo solto, subido à
      mão, sem systemd e sem tmux, e os dois env vars (`MOTOR_MODELOS`, `MOTOR_SANDBOX`)
      existiam **só na memória do processo** — para reiniciar preservando o ambiente foi
      preciso ler `/proc/<pid>/environ`. O documento afirmava o estado desejado como se fosse
      o medido, que é exatamente o defeito que os cortes de interface passaram o dia removendo
      das telas.
      Corrigido: unit de usuário `kortex-painel.service` com `Restart=on-failure` e
      `EnvironmentFile=~/painel.env` (fora do repo — caminhos absolutos da máquina, e `origin`
      é público). Exemplo versionado em `motor/motor_painel/painel.env.exemplo`.
      **Provado, não suposto:** `kill -9` no processo e o systemd devolveu pid novo em menos de
      9s, HTTP 200 depois. `loginctl enable-linger cap` → `Linger=yes`, então o serviço não
      depende de sessão aberta.
      **Duas armadilhas de operação que custaram tempo e ficam registradas:** `npm` não está no
      PATH do ssh não-interativo (é preciso `export PATH=$HOME/.nvm/versions/node/v24.19.0/bin:$PATH`
      antes de `npm run build`), e `systemctl --user` falha em silêncio sem
      `export XDG_RUNTIME_DIR=/run/user/$(id -u)`.
- [ ] **o motor** sobe sozinho no boot — o painel sobe; missão em curso não retoma
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

## 3.9 A cadeia do canvas — o que falta para "andar pela fábrica"

O fundador descreveu a superfície que quer: laços pulsando onde o processo roda de
verdade, clicar num agente e ver o que ele está mexendo, gate mostrando o que segurou,
cada tool call visível, artefato brilhando ao passar de nó. E deu o critério de completude
mais útil que este projeto tem: **"eu conseguiria montar um jogo 3D só com essas
informações"**.

Isso não é figura de linguagem — é teste de aceite. Um jogo **não pode inventar**: renderiza
o que o estado entrega. Se o fluxo de eventos permite reconstruir a fábrica, o fluxo está
completo; se não permite, falta evento. É a regra *"a superfície nunca inventa lugar"*
(`DECISAO-canvas-e-operacao.md` §5) virada em critério mensurável.

O que ele descreveu se separa em três baldes, e a diferença importa:

**A. Já dá com o que o ledger emite** — nó, aresta, artefato passando, gate aprovando ou
reprovando. Existem `aresta.fluxo`, `validador.rodou`, `portao.aprovado`,
`artefato.atualizou`. Falta desenho, não dado.

**B. Falta evento, não semântica** — cada tool call, o que o gate segurou, clicar na linha e
ver o log. Hoje o `motivo` de `validador.rodou` vem **vazio quando aprova** (medido:
foi preciso reproduzir o portão à mão para ver a evidência). Falhas de rota agora emitem
`modelo.falha` com coordenada e classe; ausência de rota emite `registro.sem_executor` e
não é confundida com veredito inválido (issues #12/#20, fechado em 2026-08-20). Some a
coordenada de estação em evento de falha (ROADMAP Now 6)
e a projeção incremental por `(fonte, seq)` (ROADMAP Now 5, declarada *"precondition for any
canvas surface"* — `run_id` resolve identidade, mas não substitui o cursor local; falta o
servidor detectar todos os buracos).

**C. Falta semântica — não existe no modelo.** Dois casos:
- *"clico no agente e vejo o que ele está mexendo, um chat, e posso interceptar"* — **não há
  "durante"**. O executor é um `-> str`; ele devolve um bloco e acabou. Sem laço não há o
  que interceptar. Isto é a decisão de harness
  (`DECISAO-harness-e-costura-de-execucao.md`).
- *"um agente do nada perguntando algo a outro"* — **consulta não existe**. Não confundir com
  **handoff** (artefato atravessando a fronteira, já decidido e tipado): consulta é
  request/response que **não avança o artefato**, topologia diferente. Aresta de consulta
  livre transforma o DAG certificado em grafo sem limite — o *"n8n de fios livres"* que
  `DECISAO-ciclo-de-vida-workflow.md` §10 proíbe. **Proposta a decidir:** consulta vira
  **capacidade declarada do nó** ("este nó pode consultar a casa X"), cada consulta sendo
  evento logado, com teto e proveniência. Parece espontânea na tela; é declarada e contida
  no registro.

**Andar é casa, não container de workflow.** O workflow atravessa andares por desenho — é o
caso normal. O canvas já tem as duas vistas (`ledger/Grafo.jsx` para a run,
`andares/VistaAndares.jsx` para a pilha de casas) e **deliberadamente não desenha ligação
entre andares**, porque o artefato tipado ainda não existe: desenhar antes seria inventar
relação.

### A ordem que o estado sugere

1. **contrato tipado com proveniência** (V5+V7) — destrava ligação entre andares, composição,
   orquestrador, modo aplicação, adoção de harness e o desenho da linha no canvas
2. **executor com laço** atrás da costura de harness — cria o "durante" que o canvas precisa
3. **os eventos do balde B** — projeção incremental, coordenada de estação, evidência no log
4. **então** a superfície tem substância para renderizar

Fazer a tela antes seria animar um processo que não emite o que ela precisa.

## 4. Se você vai desenvolver agora

**A ordem que o estado atual sugere**, não é ordem imposta:

### O contrato tipado, medido (2026-08-19)

A instrução era medir antes de construir. Medido:

**O que um artefato é hoje:** `{nome, caminho, tipo, hash}` — referência de arquivo mais
SHA-256 do conteúdo. `tipo` **não é tipo**: a spec usa `list[dict[str, Any]]` e valida
apenas que a string não é vazia. Sem enum, sem registry, sem schema, sem versão.
**Proveniência de run:** desde os issues #24/#25, eventos novos carregam `run_id` no
envelope plano; `artefato.atualizou` carrega `hash` como payload opcional pareado com a
identidade do envelope. O schema mantém eventos legados sem esses campos válidos.

**O achado dos issues #24/#25:** o `hash` era calculado e jogado fora duas vezes. Agora
entra em `artefato.atualizou` e o `run_id` entra no envelope; no resumo de serviço, a lista
legada de artefatos permanece compatível e os hashes ficam em `artefato_hashes` por caminho.

**A armadilha:** o schema de eventos v2 é **fechado** — campo desconhecido falha, campo
listado é obrigatório salvo se estiver em `CAMPOS_OPCIONAIS`. E `LogEventos` revalida
todas as linhas ao reabrir. **Campo obrigatório novo faz run antiga deixar de abrir.**
Proveniência tem que entrar opcional, com distinção explícita entre legado e contrato novo.

**Tamanho:** ~15–20 pontos de contrato (não 2, não 56). Fatia vertical com migração
compatível e testes: **300–600 linhas**. Atravessando casas e orquestrador: **800–1500**.
Chega a 2000 só se as sete frentes forem entregues juntas — e aí é escopo de integração,
não tamanho do artefato.

**O `proveniencia` do curador NÃO serve de base.** É string que identifica origem de caso
held-out, não linhagem de output. Reusar misturaria identidade de dataset com proveniência
de artefato.

**A conclusão que contraria o discurso, e é a parte que importa:** *"a peça é menor no
núcleo e maior na fronteira"*. O risco real não é escrever um `ArtefatoSpec` — é **decidir
qual identidade atravessa a fronteira e impedir que serviço, canvas, curador e orquestrador
voltem a reduzir isso a caminho + string**, que é exatamente o que os quatro fazem hoje.

**Consequência para a ordem:** o trabalho difícil é decisão de arquitetura, não implementação.
Uma primeira fatia barata e independente já existe: **parar de jogar o `hash` fora**.

---

**1. Contrato tipado com proveniência (V5+V7).** O tijolo. Apareceu como pré-requisito de
**sete** coisas distintas em 2026-08-19: ligação entre andares no canvas, composição entre
casas, orquestrador, modo aplicação, adoção de harness, handoff tipado e a linha de consulta.
**Antes de construir, meça o tamanho dele** — concentrar sete frentes numa peça não medida é
risco, não plano.

**2. Os eventos que faltam** — issues #12 e #20, projeção incremental por `seq` (ROADMAP
Now 5) e coordenada de estação (Now 6). É o balde B da §3.9, destrava a superfície, e são
baratos e independentes entre si.

**3. Executor com laço**, atrás da costura de harness. Cria o "durante" que o canvas precisa
e tira o executor do `-> str`. Depende de (1).

**4. Issue #7** — moeda de contenção para rota grátis. **Depende do fundador**: exige
evidência de faturamento real nas contas dele, e o `omniroute pricing` **não** serve (§5).

Fora de ordem, quando houver tempo: #18, #16, #13, #6, #8 (esta última está enunciada
ao contrário — ver §5).

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
- **OmniRoute está em configuração padrão**, levantado em 2026-08-19. Os mecanismos de
  resiliência existem e estão nos defaults: `waitForCooldown` e `comboCooldownWait`
  ligados, `providerBreaker` com thresholds (OAuth 8/5/60s, API key 12/7/30s),
  `providerCooldown` **desligado**, e **nenhum combo configurado** — ou seja, **não há
  cadeia de fallback explícita**, só a mecânica default. `resilience config set` aceita
  `--threshold`, `--reset-timeout`, `--base-cooldown`; perfis existem e nenhum foi
  definido. A API administrativa exige chave: `pricing` e `lockouts` responderam **401**
  (o `OMNIROUTE_API_KEY` não está setado), então ausência de dado ali **não** é ausência
  de configuração.
- **`omniroute sync` MOVE CREDENCIAL.** O bundle padrão inclui `providers` e `keys`, e
  `providerConnections` carrega `accessToken`, `refreshToken` e `apiKey`. Reconciliar Mac
  (22 conexões) com runner (5) **não é operação benigna de config** — trate como
  movimentação de segredo.
- **O ledger não era durável, e o quanto foi medido (2026-08-20, issue #22).** No checkout
  de produção: **29 workspaces de run em disco, 26 explicados** por log próprio ou por evento;
  **49 artefatos de produto, 40 com `artefato.atualizou`** — 9 órfãos. Mais 109 arquivos de
  ferramenta (`__pycache__`, `.pytest_cache`) que **não** são artefato e inflariam o número.
  Consequência para qualquer análise sobre o corpus: **a distribuição de `tipo` é sobre o que
  sobrou, não sobre o que houve.** Duas armadilhas de medição que custaram caro e ficam
  registradas: (a) nem toda pasta sob `runs/` é uma run — `caixa`, `despachos`, `orcamento` e
  `lift-docs-*` moram lá e contá-las levava de 3 para 8 "runs órfãs"; (b) o `caminho` do evento
  é **absoluto** e aponta para o checkout onde a run rodou, então comparar por caminho absoluto
  faz **todo** artefato virar órfão noutra máquina. A identidade estável é
  `<run_id>/artefatos/<resto>`.
- **`run_id` no envelope e `artefato.atualizou` legado sem identidade** (issues #24/#25,
  2026-08-21). Eventos novos carregam `run_id` no envelope e `hash` no payload do artefato,
  permitindo às superfícies identificar a run produtora sem inferir pelo caminho. Linhas
  legadas ficam num único balde sem proveniência; o schema continua aceitando-as.
- **`t` do envelope é relativo, não epoch.** Medido de 0.028 a 5252.231 no log de produção:
  não dá para datar evento nenhum. Tratar como duração desde o início da run, nunca como hora.
- **Snapshot de rotas grátis vencido** (117h contra limite de 24h). O motor recusa com
  *"adiantar só a data não prova gratuidade nem disponibilidade"*. Disponibilidade (HTTP 200)
  **não** é gratuidade — remedir exige olhar consumo no provedor.
- **A #24 destravou o contrato, não o corpus** (medido 2026-08-22, checkout de produção).
  Dos 47 eventos `artefato.atualizou`, **0 carregam `hash`** e **0 carregam `run_id`** — 47 de
  47 são legado, porque **nenhuma run executou desde o merge**. O contrato está bem feito e
  foi conferido no código, não só no log: os dois emissores passam `hash=`, e o schema exige
  **tudo-ou-nada** (`run_id` e `hash` juntos, com `hash` casando `[0-9a-f]{64}`) — não há
  meio-estado possível. O que falta é run.
  **A armadilha de medição que isso cria, e que já enganaria alguém:** o ledger tem **290
  eventos com `run_id`** e nenhum prova nada sobre a #24 — são todos `custo.*`
  (`custo.reservado` 144, `custo.reconciliado` 143, `custo.bloqueado` 3), proveniência
  monetária anterior. Dos 1194 estruturais, zero. Contar `run_id` sem separar por tipo de
  evento conclui o oposto da verdade.
  Consequência prática para a estante: o campo *"na run"* **continua impossível**, e
  *"revisões: N"* **já era possível** antes da #24, por caminho — 7 de 40 caminhos escritos
  mais de uma vez. Mas por caminho conta **escrita**, não mudança: duas escritas idênticas
  contam 2, então 7 é teto, e as revisões reais podem ser 0. É isso que o hash conserta.
- **O painel ainda depende de rede para abrir** (issue #26, medido em 2026-08-21 sobre o
  `dist/` de `db539a1`). Depois dos cortes, os **únicos** hosts externos que sobraram no
  bundle são `fonts.googleapis.com` e `fonts.gstatic.com`, em `app/index.html:7-9`. Nenhum
  host externo de *código*: a CDN do unpkg saiu junto com o `Grafo3D` antigo. A tela abre sem
  internet (as fontes têm fallback), mas com tipografia diferente e depois do timeout de duas
  conexões que não respondem — num painel cujo lugar é um runner de LAN. Não é regressão dos
  cortes: já estava em `eb14268`. **Não confundir** com `motor_painel/grafo3d.html` + rota
  `/grafo3d`, a superfície legada que serve quando não há `app/dist` e continua com CDN de
  código — assunto separado, ainda em aberto.
- **Uma falha intermitente registrada em vez de descartada** (issue #27).
  `test_caixa.py::test_interrupt_cria_nota_e_decisao_conclui` caiu **uma vez** em 2026-08-21 e
  não reproduziu: passou isolada 8/8, nas duas execuções completas seguintes do agente, na
  minha do ramo e na minha da `main` mergeada. Nada no ramo tocava a caixa. Fica aberta porque
  as duas explicações — ruído de ambiente e corrida sob carga — cabem igualmente, e a segunda
  é cara se estiver certa. **Armadilha de medição aprendida no mesmo dia:** rodar duas suítes
  no mesmo checkout produz falha falsa — foi assim que eu vi
  `test_docker_runner_timeout_remove_arvore_container` cair, e o erro era meu, não do ramo.
- **Higiene do workspace de testes medida e protegida** (issue #28, 2026-08-21). O
  `GerenciadorJobs` agora exige `workspace_base` explícito; o MCP exige `MOTOR_WORKSPACE`,
  e a suíte usa `tmp_path` nos construtores que poderiam abrir logs. Uma fixture recursiva
  compara `motor/runs` antes/depois, nomeia cada caminho novo ou alterado e ignora somente
  caches declarados (`.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `__pycache__`, `.pyc`/`.pyo`).
  Duas suítes sequenciais ficaram em **146 → 146** diretórios, com **1290 passantes, 35
  pulados e só E-02 falhando** em cada uma. Restam 131 diretórios com `log.jsonl` vazio no
  checkout, preservados para decisão humana; não foram apagados. A decisão do `db_path="motor.db"`
  relativo ficou separada na issue #2, aberta após medir seis arquivos sob `Projetos`, um deles
  fora do `motor/` esperado.

---

## 5.1 Decisões pequenas que ficaram travadas em teste

Registrado em 2026-08-19 para não se perderem: são casos em que a correção certa exige
mudar um teste que fixa contrato, e a autorização é do fundador.

- **`obter_catalogo()` joga fora `padrao` e `quando`.** Os arquivos de
  `exemplos/registro/*.md` declaram os dois; a função descarta. **`quando` é exatamente
  o metadado "quando usar" que a §E lista como pendente** para o catálogo de templates.
  Expor qualquer um quebra `test_get_dados_catalogo`, que fixa
  `set(item.keys()) == {id, nome, descricao, subagentes, versao}` com igualdade exata.
  O agente parou corretamente e manteve a chave, mudando só o valor (`versao` virou
  `None`). Acrescentar chave é mudança de contrato que o teste pega de propósito.

- **Sete páginas fazem poll do `/dados` inteiro a cada 2s** (Curador, Datahouse,
  MapaGeral, Board, Dashboard, Logs, Grafo3D). É o gargalo que
  `DECISAO-canvas-e-operacao.md` §6.1 previu — *"o gargalo será a camada de dados, não
  os pixels"* — e a projeção incremental por `seq` (ROADMAP Now 5) é o endereço.

- **`orfaos_de_artefato` varre `runs/**` a cada chamada**, e o `Datahouse` faz poll de
  2s. Irrelevante com 29 runs e 158 arquivos; vira `stat` em disco a cada dois segundos
  com milhares. Não foi cacheado de propósito: cache de contagem de disco mente calado,
  que é o defeito que a função conserta.

- **A caixa de órfãos é alarme permanente.** São runs de junho que ninguém vai
  reconstruir. Tela com alarme que nunca some ensina a ignorar alarme. Uma saída seria
  marcar um corte ("órfãos anteriores a X são dívida conhecida") — não foi feito porque
  seria decidir o que é aceitável esconder.

## 6. Como manter este arquivo honesto

- Marque `[x]` só com evidência citável. Sem evidência, é `[ ]`.
- Ao fechar um item, mova o fato medido para a §5 com a data.
- Ao descobrir que um documento antigo mente, **diga aqui qual e em quê** — como a §2 faz com
  o parecer. Não reescreva o documento antigo em silêncio.
- Issues vivem em `caiopieri/Kortex-backup` (repo privado; o código é público). Não duplique a
  lista aqui — referencie o número.
- **Audite os `[x]` de vez em quando, rodando.** Este arquivo é a superfície que diz o
  estado, e superfície que afirma mais do que sabe é exatamente o defeito que os issues #15,
  #23 e #29 corrigiram nas telas. Ele não está imune só por ser markdown.

### Auditoria de 2026-08-22

Seis afirmações `[x]` verificadas executando, não lendo:

| afirmação | veredito | como |
|---|---|---|
| painel servido na LAN por systemd | **FALSA** | processo solto, sem systemd nem tmux; env só na memória. Corrigida na §F, e o systemd foi de fato instalado depois |
| `npm ci` volta a funcionar (#16) | verdadeira | `npm ci` em pasta limpa, só com `package.json` + lock |
| despacho pela interface inclui `--sandbox` | verdadeira | `painel.py:1137` — de env, nunca do corpo HTTP |
| snapshot vencido bloqueia | verdadeira | `omniroute_orcado.py:236` — e recusa também data no **futuro** |
| `CommandRunner` default é negar | verdadeira | `grafo.py:625`, `costura_executor.py:72` |
| com `--auto`, cobertura reprovada não é auto-aprovada | verdadeira | `grafo.py:1701` — o default de `--auto` para cobertura é `escalar`, e sem juiz independente o portão **degrada para humano**, nunca libera |

**Achado lateral:** o `npm ci` reporta 2 vulnerabilidades *high* transitivas (`postcss`,
`nanoid`, via `vite`), ambas de tempo de build. Issue #31, com o motivo de não terem sido
corrigidas de imediato.

**O que a auditoria diz do arquivo:** a única mentira era sobre **infra**, não sobre o motor.
As afirmações sobre invariantes se sustentaram, e duas delas (`--auto` não aprova cobertura;
snapshot vencido bloqueia) estão implementadas com mais rigor do que a linha prometia.
