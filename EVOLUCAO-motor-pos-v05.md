# Evolução do motor (pós-v0.5) — o norte

> Para: Caio + Codex + Claude (sessões futuras). De: revisão de arquitetura, 2026-06-29.
> Companheiro de `ARQUITETURA-MCP-e-orquestrador.md` (a fronteira) e `HANDOFF.md` (a fabricação v0.5).
> Referencia `../dev-harness/docs/biblioteca-de-validadores.md` e `../../ROADMAP-META-FABRICA.md`.

## Regra de ouro

**Melhorar, não substituir.** A essência do motor está certa — ela já encarna o grafo híbrido, o gate, a
provider-agnosticidade e o princípio "músculo, não autoridade". O que vem a seguir é **aditivo**, ao longo
de eixos que a própria arquitetura já deixou em aberto. Quem propuser um redesenho que jogue fora o núcleo
está relitigando decisão travada — pare e releia esta seção.

## A essência a preservar (não relitigar)

1. **Grafo LangGraph fixo + WorkflowSpec dinâmica.** Feature nova = mudança na spec (dado), não nó novo no
   grafo (código). Esta é a coluna vertebral.
2. **Nós são funções puras** que falam com uma capacidade (`cliente.chamar(papel, prompt)`); roteamento
   modelo↔papel em `modelos.py`. Sem chamada de modelo direta no grafo.
3. **Padrão certificado v0:** fan-out → verificador adversarial por subagente (retry ≤ max) → avaliador de
   cobertura **antes** da síntese → gate via `interrupt()`. Subagente reprovado vira lacuna **por código**.
4. **Eventos JSONL = auditoria** (fonte da verdade); checkpointer SQLite = só resume.
5. **Motor = músculo, não autoridade.** Não decide permissão, não classifica risco, não mede dinheiro, não
   fala pelo dono. Gate sobe **cru**; classificação/cláusula pétrea moram no porteiro (Jarvis).
6. **Superfície MCP fina** (despachar/status/responder_gate); jobs duráveis, não-bloqueantes.

## Estado dos vetores (2026-06-29)

- **Fase C COMPLETA** (não estava aqui quando o doc nasceu): prevenção (rota de dependência em ondas) +
  escalada de tier + reconciliação na fonte em loop bounded. Validada em run real. Isso é o
  "reprovado vira lacuna por código" generalizado para correção upstream.
- **V3 em curso/adiantado:** curador tem observador + propositor por slot + telemetria-por-modelo +
  livro-razão de custo — tudo **read-only**. Falta a fatia 3 (agir: sombra + certificação).
- **V2 em curso:** handoff do esquema de eventos tipados + canal MCP escrito.
- **V5 parcialmente real:** a rota `grafo_dependencias` já roda com handoff entre nós via `deps_txt`; a
  formalização do contrato tipado de handoff (spec v0.2) é o que falta.
- **Paperclip** (MIT) confirmou o V4: o control-plane (orçamento/eventos/approvals/UI) é roda pronta a
  reusar **na camada das casas**, nunca no motor. Ver `../LEIA-PRIMEIRO.md` §3.

## Os vetores de evolução (aditivos)

### V1 — Nós validadores determinísticos como primitiva da spec (o grande)

Hoje os validadores do grafo são LLM (verificador subagente, avaliador de cobertura). A
`biblioteca-de-validadores.md` mostra que muitos gates **podem e devem ser determinísticos** (teste,
schema, compile, matemática, simulação, SAST). A evolução: a WorkflowSpec passa a declarar **nós
validadores determinísticos**, não só subagentes.

- **Por que cabe na essência:** continua sendo "a spec é a dinâmica" e "nó é função pura que chama uma
  capacidade" — só que a capacidade, num nó validador, é um **algoritmo** (`rodar pytest`, `validar
  schema`, `recalcular número`) em vez de `cliente.chamar`. O "reprovado vira lacuna por código" já existe;
  generaliza.
- **É o grafo híbrido virando real:** agente = peça pensante; validador determinístico = a verdade. É o
  coração anti-alucinação, e é onde estamos à frente do Paperclip ("Enforced Outcomes" não-feito).
- **O que NÃO fazer:** não transformar isso em motor de workflow visual nem em DSL gigante. É um novo *tipo
  de nó* na spec, com a mesma disciplina de versão (padrão novo = spec v0.2, decisão do Caio).

### V2 — Contrato de evidência + esquema de eventos tipados

Cada nó (pensante ou validador) emite evento tipado com **referência de evidência** (`validador.rodou`,
`gate.passou`/`gate.reprovou` + ref, `checkpoint.pediu_humano`). Estende `eventos.py`, não muda o núcleo.

- **Por que importa:** esse stream **é** a interface viva e o ponto de interceptação — o controle estilo
  Paperclip (e mais) que o Caio quer cai daqui, não é feature à parte. É o item "esquema de eventos
  motor→superfície" do roadmap.

### V3 — Curador opera a biblioteca de gates (a catraca)

`curador.py` já faz observador + propositor (read-only). A trajetória travada segue: fatia 3 (teste em
sombra + certificação) → então o curador pode **propor criar/melhorar/aposentar validadores** e mudanças de
roteamento. É a auto-evolução do processo.

- **Disciplina inalterada:** read-only → sombra → aplicar; só dado gate-verificado treina (anti-collapse);
  curador nunca aplica sem certificação. Criar/apagar gate é mudança governada, não autônoma silenciosa.

### V4 — Fronteira fractal: as casas ficam ACIMA do motor

A direção "softwarehouse / hardwarehouse / conglomerado" é control-plane (org chart, orçamento, tickets,
coordenação entre papéis). Pela decisão pétrea #5, **nada disso entra no motor.** O motor roda *um* processo
(um artefato) com maestria; a casa coordena muitas runs; o orquestrador coordena casas.

- **Consequência prática:** o control-plane (a "roda inventada" do Paperclip, MIT) é emprestado/reusado na
  **camada da casa**, não no motor. Resistir à tentação de inchar o motor com orçamento/permissão/org é o
  que mantém ele "músculo". O motor já está protegido por essa decisão; este vetor só a reafirma.

### V5 — WorkflowSpec v0.2: dependências e handoff entre nós

Os exemplos já apontam pra grafos com dependência (`grafo-dep-minimo.json`, `hardware-diagnostico.json`).
A v0.2 formaliza **handoff baseado em contrato** entre nós (e, mais tarde, entre casas): a saída de um nó é
um artefato tipado com evidência que o próximo consome — não conversa solta.

- **Disciplina:** novos padrões (chain, tournament, dep-graph rico) entram por **versão de spec
  certificada**, um de cada vez, como já manda o HANDOFF. v0.5 certifica fan_out_sintese primeiro.

### V6 — Fábrica de especialistas (o curador-supervisor que cria modelos)

A ambição mais profunda do curador: criar **"monstrinhos"** — modelos pequenos, baratos e
super-especializados por papel (backend, CAD…) que entregam com maestria. É o destino do flywheel, e é o
vetor de **maior risco** (model collapse). Por isso a disciplina é parte do design, não opcional:

- **A régua é o gargalo, não o treino.** Não se cria especialista melhor do que a capacidade de *medir*
  "melhor". Rollout vertical por vertical, ordenado por **quão barato é o grader** (software cedo —
  compila/testa/lint/SAST; CAD/jurídico muito depois). É a regra "gate antes de flywheel" levada ao treino.
- **Conhecimento antes de peso.** Boa parte da maestria é RAG + ferramentas + grafo de conhecimento — sem
  treino, sem collapse. Fine-tuning/destilação são os últimos 10%, só com volume + estabilidade + grader.
- **Treinar é uma run gated do motor** (recursão): o curador despacha um workflow "treine X" — coleta sob
  gates de licença → fine-tune → **eval no held-out como nó validador determinístico (é o V1!)** → promove
  só se bater o titular em **qualidade E custo** (o custo vem do livro-razão; é a conta de ROI).
- **Coleta massiva é uma "data-house" separada** (scraping/transcrição/limpeza, sob gates de IP/licença). O
  curador é o cérebro (decide *o que* falta via "gap map" e avalia o resultado), não o operário.
- **Proveniência no treino:** todo especialista carrega que dado/modelo/versão o produziu (indebugável sem).
- **Alocação é a outra metade** e já existe: o propositor por slot + roteamento por tier/custo é onde o
  monstrinho novo entra. Criar especialista alimenta a alocação que o curador já governa.

**Disciplina:** só dado gate-verificado treina (anti-collapse); âncoras de ouro detectam deriva; **prove UM
especialista (backend) ponta a ponta** antes de generalizar. Nada disso entra no motor-kernel — o treino é
orquestrado pelo curador/casas usando a máquina do motor, não é nó hard-coded no grafo.

## Sequência sugerida (depende, não importância)

1. **V2 (esquema de eventos)** — EM CURSO. Barato, destrava interface/controle e instrumenta tudo. Primeiro tijolo.
2. **V1 (nós validadores determinísticos)** — o salto de qualidade anti-alucinação. Começar pela família
   mais barata (schema/contrato + teste), que casa com a vertical de software.
3. **V3 (curador catraca)** — fundação read-only FEITA (observador+propositor+custo); o próximo degrau é a
   **fatia 3** (sombra + certificação), o ponto em que o curador começa a *agir*. Timing casa com a troca
   de provedor do Caio.
4. **V5 (spec v0.2 dep/handoff)** — parcialmente real (grafo_dependencias); formalizar o contrato tipado
   quando uma run pedir.
5. **V6 (fábrica de especialistas)** — Later, gated pelo V1 (grader) + V3 fatia 3 + livro-razão de custo.
   Prove UM especialista antes de generalizar.
6. **V4** é guarda permanente, não tarefa: vale em toda decisão ("isso é músculo ou autoridade?").

## O que NÃO fazer (guardas)

- Não meter company/orçamento/org-chart/permissão no motor (vive na casa).
- Não trocar fan_out_sintese por padrão novo sem certificar; padrão novo = spec v0.2, decisão do Caio.
- Não fazer o motor classificar/decidir gate; ele sobe cru.
- Não criar parser mágico pra prosa de LLM; ajustar prompt, não topologia.
- Não deixar o curador aplicar mudança sem sombra+certificação.

## Onde isto pode dar errado

- **Validador determinístico mal escrito** vira falso conforto (teste que não testa, schema frouxo). A
  catraca ajuda, mas validador também precisa de revisão.
- **Inchaço de escopo:** a gravidade das casas/control-plane vai puxar funcionalidade pra dentro do motor.
  Resistir é a decisão #5; quando em dúvida, fica fora.
- **Spec virando linguagem de programação.** Se a WorkflowSpec começar a precisar de lógica condicional
  rica demais, é sinal de que algo que devia ser nó/código virou dado. Reavaliar antes de crescer a DSL.
- **Evoluir sem run real.** Cada vetor estreia num uso real (Logisti/softwarehouse), não em abstrato —
  mesma regra de validação-primeiro de sempre.
