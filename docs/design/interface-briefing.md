# Briefing de design — a interface viva da meta-fábrica

> Para: Claude Design · De: Caio · Data: 2026-06-29
> Substitui qualquer briefing anterior. Documento autossuficiente: não exige conhecer as conversas que
> o geraram. Referências internas no fim.

---

## 1. O que é a meta-fábrica (contexto mínimo)

A meta-fábrica é um **simulador de organização**: recebe um objetivo ("construa o módulo X", "projete a
peça Y") e instancia o time de papéis especialistas que ele exige — planner, arquiteto, engenheiros
(hardware, mecânico, firmware, software), QA, jurídico/patente, designer, mantenedor — rodando o
processo inteiro dentro de um **motor** (engine LangGraph, headless) com gates e evidências. Hoje
produz artefato intelectual (software, specs, docs, design); no futuro, ponte com o físico.

O dono opera como um diretor estilo "Tony Stark / Jarvis": tem a ideia, delega, **acompanha**,
intercepta quando quer, ajusta, e o resto roda sozinho. A função-objetivo do produto inteiro é
**minimizar o tempo-até-decisão do humano e o retrabalho.**

## 2. O que estamos pedindo ao design

Desenhar a **interface viva** dessa fábrica: a superfície onde o dono *vê o processo rodando*,
*acompanha agentes, modelos e fluxos*, e *intercepta sem parar o trabalho*.

Queremos o **design completo da visão** — todas as capacidades, inclusive as que ainda não existem no
motor. Cada capacidade vem com um **status de maturidade** marcado (§10), pra que este documento sirva
também de mapa do que já funciona e do que ainda falta construir. O design deve abraçar a ambição
inteira; o status diz o que é real hoje e o que é aspiracional.

A metáfora-guia do dono:

> "Como ver o desenho do cérebro trocando sinais entre neurônios — e poder entrar nas salas da empresa,
> assistir os funcionários trabalhando, dar palpite ou parar pra ajudar, depois sair e seguir vendo em
> macro. Ver o CAD se atualizando numa janelinha enquanto outro agente roda entre bancos de dados, com
> as conexões brilhando e a engrenagem do banco girando porque está sendo usado."

## 3. Princípio inegociável: interface PRÓPRIA da meta-fábrica; o motor é headless

Esta é a **interface própria da meta-fábrica** — ela é autossuficiente: tem o motor *headless* (que
fabrica e expõe estado) **e** a sua própria superfície (que vê e controla). A interface **não é** o motor:
o trabalho pesado vive no motor headless; a tela **renderiza o stream de eventos** que o motor emite (ver
§10) — não calcula nem decide nada do processo, só mostra e permite intervir. A fronteira é **MCP**.

**Flint não é esta superfície.** O Flint (app de notas do dono) é um **projeto separado** que *pode*
integrar a meta-fábrica como **cliente externo opcional**, consumindo o mesmo stream MCP — a meta-fábrica
**não depende dele**. O design pedido aqui é o da **interface própria** da meta-fábrica; o canvas/primitivos
do Flint citados adiante são **referência de padrões** (frames, linhas nomeadas, zoom) que um cliente como
o Flint poderia reusar, não um requisito de que a superfície seja o Flint.

Modelo de frames (vale pra interface própria e para qualquer cliente que integre): cada agente/sala/
artefato é um **frame**; conexões são **linhas nomeadas**; e há duas camadas sobreponíveis (grafo de
conhecimento vs grafo de atividade).

## 4. Princípios de design (os não-negociáveis)

1. **Zoom semântico é a interação central.** "Entrar nas salas" = trocar de *nível de detalhe*, não dar
   zoom de pixel. Três níveis distintos: **macro** (a fábrica/organização, projetos como regiões) →
   **meso** (o pipeline de um projeto: papéis, dependências, handoffs) → **micro** (um agente: ação
   atual, chamadas de ferramenta, raciocínio/trace, o artefato que ele edita ao vivo).
2. **Vivacidade = projeção de sinal real. Zero mentira decorativa.** Cada brilho, pulso, engrenagem ou
   partícula mapeia um evento real do motor (ferramenta ativa, custo subindo, dado fluindo numa aresta,
   gate passou/falhou). Nada anima "só pra ficar bonito". Se não há sinal, não há animação.
3. **Observar por padrão, intervir sob demanda, não-bloqueante.** O dono assiste sem atrapalhar; quando
   intervém, o agente segue trabalhando (ver §9).
4. **Vivo + rebobinável.** Além do tempo real, uma linha do tempo permite *replay* de qualquer run
   passada como filme (o mesmo log de eventos desenha os dois).
5. **Duas camadas sobreponíveis:** o **universo de conhecimento** (o que se sabe — grafo de notas/dados,
   estático-ish) e a **atividade** (o que está acontecendo agora — agentes, fluxos). São coisas
   diferentes; a mágica é transitar entre elas. (No Flint isso já é a distinção "grafo de conhecimento"
   vs "grafo de workflows".)
6. **Beleza a serviço da legibilidade.** A estética neuronal deve tornar o estado *instantaneamente
   legível* — não é enfeite. Em 1 segundo o dono entende: o que está rodando, o que travou, o que custa,
   o que pede atenção.

## 5. Quem usa e o que precisa fazer (jobs)

Usuário único e exigente (o dono). Tarefas, em ordem de frequência:
- **Dar um norte e soltar** — "tive uma ideia, faça X" → ver o pedido virar pipeline e começar a rodar.
- **Acompanhar em macro** — relance de olho: tudo verde? algo travado? quanto está custando?
- **Mergulhar numa sala** — entrar no nível micro de um agente pra ver *como* está fazendo.
- **Interceptar** — dar um palpite, sugerir, parar ou assumir — sem derrubar o resto.
- **Aprovar checkpoint** — validar o de cima (design, escopo) antes de comprometer o de baixo (toda a
  documentação, produção). É o anti-retrabalho central: o sistema **para e pede** nos pontos certos.
- **Rebobinar** — entender depois o que aconteceu numa run.

## 6. A linguagem visual viva (mapeada a sinais reais)

Cada elemento abaixo deve corresponder a um evento do §10:
- **Aresta em fluxo** (animada) = dado/handoff passando entre dois nós agora. Aresta apagada = inativa.
- **Nó pulsando / borda acesa** = agente ativo trabalhando. Opaco = ocioso. Tracejado = na fila.
- **Engrenagem girando** num banco = store sendo lida/escrita agora.
- **Cor** = saúde/estado: ativo, ocioso, aguardando, **gate passou/reprovou** (verde/vermelho), **pede
  atenção** (âmbar — ex.: o sistema sugere um modelo melhor).
- **Janelinha viva** dentro do nó = preview do artefato se formando (o CAD desenhando, o código sendo
  escrito, o doc tomando forma).
- **Indicador de custo** sempre visível (ex.: "R$ 0,42 nesta run") — a missão é "cada vez mais barato",
  então o custo é cidadão de primeira classe, não escondido.

Estética da interface PRÓPRIA da meta-fábrica (no espírito flat/fluido do Flint, mas é a nossa): flat,
fluido, sem travar; performance é princípio inegociável.

## 7. Interceptação — protocolo de quatro níveis

Quando o dono entra numa sala e fala, ele escolhe o *nível de presença*:
- **Observar** — só assiste. Default.
- **Sugerir (sussurro)** — injeta um comentário que o agente capta no **próximo checkpoint**; não
  bloqueia, o trabalho continua. ("nossa, viu aquela folga ali na peça?")
- **Parar** — pausa o agente pra conversar/corrigir.
- **Assumir** — toma o controle daquela tarefa.

O design precisa comunicar claramente que **sugerir não para** — o "ele continua sozinho" é a sensação
central. Esses níveis são a mesma coisa que os gates de humano-no-loop do motor, vistos como interação.

## 8. As visões / níveis de detalhe

- **Macro — a fábrica.** Projetos como regiões/salas; saúde e custo agregados; o que pede atenção
  salta. É o "ver em macro" depois de sair de uma sala.
- **Meso — o pipeline de um projeto.** Os papéis como nós, dependências como arestas (ex.: firmware
  depende do contrato de interface do hardware), handoffs, o que está pronto/rodando/na fila/aguardando
  gate. É o mockup de referência.
- **Micro — um agente.** Ação atual, sequência de chamadas de ferramenta, o raciocínio/trace, e o
  artefato vivo. É "entrar na sala e ver o funcionário trabalhando".

## 9. O contrato de dados (o que existe pra mostrar)

A tela consome um stream de eventos tipados do motor (via MCP). O design pode assumir que estes
existem — desenhe em torno deles, não invente estado que o motor não emite:

`agente.iniciou` · `agente.concluiu` · `ferramenta.chamada` · `aresta.fluxo` (origem→destino) ·
`gate.passou` / `gate.reprovou` · `custo.tick` (run/modelo/projeto) · `artefato.atualizou` (preview) ·
`modelo.roteado` (papel, tier, modelo) · `curador.sugeriu` (ex.: "use o modelo X aqui") ·
`checkpoint.pediu_aprovacao` (o ponto onde o sistema para e espera o humano).

> **Status (2026-06-29):** o esquema tipado + o canal de stream MCP (`metafabrica.eventos(job_id, desde)`,
> polling incremental) estão **em construção ativa** (handoff escrito). Os eventos `aresta.fluxo`,
> `custo.tick` e `artefato.atualizou` estão sendo adicionados; `modelo.roteado` e a telemetria por modelo
> já existem. Estes nomes são a forma; o design não depende dos campos exatos, mas sim de *que estados
> existem*.

## 10. Status de maturidade — o que funciona, o que é aspiracional

Desenhe **a visão inteira**. Esta tabela existe pra que o design seja honesto sobre o que renderiza
dado real hoje e o que é projeção do futuro — e pra que a própria tela possa, mais tarde, distinguir
visualmente "isto está vivo" de "isto ainda é maquete". Estados:
**Funciona** (o motor já produz/emite) · **Parcial** (existe cru, falta polir/expor) · **Não existe**
(aspiracional; depende de fase futura).

| Capacidade | Status | Realidade hoje / depende de |
|---|---|---|
| Visão **meso** (pipeline de uma run) | Parcial | O motor já roda um grafo fan-out-and-synthesize com gate do fundador; dá pra visualizar **uma run real**. Time rico de papéis (hardware, jurídico…) ainda não. |
| Visão **macro** (a fábrica, vários projetos) | Não existe | Depende de múltiplos projetos rodando no motor. |
| Visão **micro** (trace de um agente) | Parcial | Eventos já saem em JSONL (telemetria por papel/tier). Raciocínio ao vivo e artefato editável: não. |
| **Arestas em fluxo / liveness** | Parcial | Telemetria por papel/tier **e por modelo** já existe; **Fase C** dá ondas/handoffs entre nós (matéria-prima da animação meso). Falta só o esquema de eventos tipado (§9, em build) expor `aresta.fluxo`. |
| **Interceptar: parar / aprovar** | Funciona | O gate do fundador (`interrupt()`) já para a run e espera o humano. |
| **Interceptar: sugerir (não-bloqueante) / assumir** | Não existe | Precisa do canal de sussurro e do take-over. |
| **Janelinha de artefato vivo** (CAD/código se formando) | Não existe | Depende da vertical existir (CAD não existe; código é parcial). |
| **Custo visível na tela** | Parcial | **Livro-razão de custo FEITO** (tokens+tempo+$ por run/modelo, via tabela de preço). O dado existe; falta só expor na tela (e o evento `custo.tick`). |
| **Curador sugere modelo** ("use X aqui") | Parcial | **Curador-fundação completo** (read-only): observador + propositor por slot (com piso e ciente de travas) + custo. A sugestão e o "evitar" já saem — por CLI, não na tela ainda. |
| **Replay / linha do tempo** | Não existe | O log de eventos (parcial em JSONL) é a base; a feature de rebobinar não. |
| **Grafo de conhecimento** (universo de dados) | Parcial | Semente em md (Obsidian/memória) existe; grafo visual federado não. (Um cliente externo como o Flint poderia renderizá-lo.) |
| **Editor de workflow** (montar pipeline à mão) | Não existe | Futuro; **esta peça é visualização, não autoria.** Pode ser desenhado, marcado como futuro. |

Uma sugestão de design que nasce disso: a interface pode ter um **modo "maquete" vs "ao vivo"** — partes
sem dado real aparecem claramente como simulação/placeholder, e "acendem" quando o motor passa a emitir
aquele sinal. Isso transforma a própria tabela acima em mecânica de produto: o dono *vê a fábrica sendo
construída* à medida que cada capacidade sai do "não existe" pro "funciona".

Restrições que valem pra tudo: **light e dark mode**, flat, fluido, performance inegociável (estética
própria da meta-fábrica, no espírito flat/fluido do Flint).

## 11. Critério de sucesso

Em 1 segundo de relance, o dono sabe: o que está rodando, o que travou, o que custa, o que pede atenção.
Em 1 clique, ele entra numa sala. Em 1 gesto, ele sussurra sem parar nada. A tela parece *uma fábrica
viva sendo observada*, não um dashboard de métricas.

---

### Referência visual concreta: Paperclip (MIT)

O [Paperclip](https://github.com/paperclipai/paperclip) já construiu, em produção, várias destas telas —
use como **inspiração direta** (não como gabarito a copiar pixel-a-pixel; a nossa estética é neuronal/viva
e própria): o **dashboard** de saúde/custo; a **thread de uma run com timeline + stop/cancel** (= a nossa
interceptação "parar"); a **Conference Room** (chat com o "CEO" + feed ao vivo); o **org chart** das
casas/agentes. O que eles NÃO têm e é nosso diferencial a desenhar: o **zoom semântico** macro→meso→micro,
a **vivacidade neuronal** mapeada a sinal real, o **artefato vivo** dentro do nó, e o **modo maquete↔ao
vivo**. Estude a forma deles; vista a alma neuronal/viva (própria) da meta-fábrica.

### Referências
- **`../LEIA-PRIMEIRO.md`** — a visão inteira do sistema, as camadas e o estado atual (leia primeiro).
- Mockup conceitual de partida: gerado na conversa de planejamento (nível meso, pipeline do "Drone v1").
- `Flint.md` (no repo do Flint) — um cliente externo que *pode* integrar a meta-fábrica; canvas,
  primitivos, os dois grafos, IA-harness (referência de padrões reusáveis, não a superfície oficial).
- `../ROADMAP.md` — onde esta interface se encaixa nas fases.
- `../../motor/docs/ARQUITETURA-MCP.md` — a fronteira MCP (como a tela fala com o motor headless).
- `../../dev-harness/docs/motor-entrega-profissional.md` — gates, evidências, papéis (a lógica que a tela mostra).
