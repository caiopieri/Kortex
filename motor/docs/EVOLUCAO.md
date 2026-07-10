# Evolução do motor (pós-v0.5) — o norte

> Para: Caio + Codex + Claude (sessões futuras). De: revisão de arquitetura, 2026-06-29.
> Companheiro de `ARQUITETURA-MCP.md` (a fronteira) e `../handoffs/HANDOFF.md` (a fabricação v0.5).
> Referencia `../../dev-harness/docs/biblioteca-de-validadores.md` e `../../docs/ROADMAP.md`.

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

## Estado dos vetores (2026-07-03)

- **Fase C COMPLETA** (não estava aqui quando o doc nasceu): prevenção (rota de dependência em ondas) +
  escalada de tier + reconciliação na fonte em loop bounded. Validada em run real. Isso é o
  "reprovado vira lacuna por código" generalizado para correção upstream.
- **V1 FEITO:** nós validadores determinísticos (`schema_json`/`contem`; test/compile via nó ferramenta) já são primitiva da spec;
  reprovação re-dispara o alvo via reconciliação. **RAG: lift de recuperação provado (medidor v3,
  2026-07-04)** — a evidência v2 "0/3→3/3" caiu (red-team item 3); a régua refeita (fatos
  não-adivinháveis, 3 braços, tempdir isolado) bateu o critério pré-registrado (1/5 · 0/5 · 5/5).
  Síntese: não medida. Lição estrutural: **run de experimento dentro do repo contamina** (o modelo
  lê os docs pelo filesystem) — isolamento em tempdir é obrigatório. Ver `../../LOG-VERIFICACAO.md`.
- **V2 FEITO:** 48 eventos tipados (`eventos_schema.py`, guard anti-drift) incluindo os de superfície
  (`aresta.fluxo`, `custo.tick`, `artefato.atualizou`, `validador.rodou`, `rag.consultado`) + superfície MCP
  (`despachar/status/responder_gate/resumo/eventos`).
- **V3 adiantado:** curador tem observador + propositor por slot (com **custo_usd real** no desempate) +
  telemetria-por-modelo + livro-razão de custo — tudo **read-only**. Falta a fatia 3 (agir: sombra +
  certificação) — que é também o guardrail "melhor/pior é dado, não opinião" da edição de workflow.
- **V5 parcialmente real:** a rota `grafo_dependencias` já roda com handoff entre nós via `deps_txt`; a
  formalização do contrato tipado de handoff (spec v0.2) e a **composição entre casas** é o que falta.
- **V7 (novo) — ciclo de vida do workflow: DECIDIDO** (doc `../../docs/DECISAO-ciclo-de-vida-workflow.md`).
  Ver vetor abaixo.
- **Paperclip** (MIT) confirmou o V4: o control-plane (orçamento/eventos/approvals/UI) é roda pronta a
  reusar **na camada das casas**, nunca no motor. Ver `../../docs/LEIA-PRIMEIRO.md` §3.

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

### V7 — Ciclo de vida do workflow (catálogo, versão, autoria-como-run, composição)

Decidido em 2026-07-03; canônico em `../../docs/DECISAO-ciclo-de-vida-workflow.md`. Resumo dos pontos que
tocam o motor:

- **Template vs. missão.** Um template é um workflow nomeado (menu de papéis); a missão **instancia** e
  **seleciona** — a spec da missão é muitas vezes um **subconjunto** do template. Papéis são primitivas
  reutilizáveis; uma missão pode montar nós de templates diferentes.
- **Catálogo de workflows versionados** (metadados "quando usar"); o Orquestrador seleciona o template.
  Software = o `dev-harness` já é esse template (consenso codificado).
- **Autoria é uma run do motor** (pesquisa→síntese→rascunho de spec) — mesma recursão do V6.
- **Versão carrega evidência** (do livro-razão): certificação = versão + telemetria. É "só dado
  gate-verificado promove" aplicado à evolução do workflow.
- **Execução parcial / MVP:** perfil de disparo que solta gates/validadores/escalada → run sai **marcado
  "não-certificado"** e **fora do corpus do curador/flywheel** (anti-collapse). Pode, mas não mascara de
  certificado.
- **Composição entre casas:** artefato tipado com proveniência atravessa a fronteira (é o handoff tipado do
  V5 subindo um nível); **quem encadeia é o Orquestrador**, não o motor (decisão #5).
- **Limite de topologia inalterado:** workflow novo = spec nova (livre); **padrão novo** (topologia/controle
  novo) = versão de spec certificada (raro). O editor visual oferece só a gramática válida.

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
6. **V7 (ciclo de vida do workflow)** — decidido; o que falta é construção (catálogo/registro versionado,
   editor visual na interface, marca de run não-certificado, contrato de composição entre casas). Casa com
   V5 (spec v0.2) e V3 fatia 3 (o guardrail da medição).
7. **V4** é guarda permanente, não tarefa: vale em toda decisão ("isso é músculo ou autoridade?").

## O que NÃO fazer (guardas)

- Não meter company/orçamento/org-chart/permissão no motor (vive na casa).
- Não trocar fan_out_sintese por padrão novo sem certificar; padrão novo = spec v0.2, decisão do Caio.
- Não fazer o motor classificar/decidir gate; ele sobe cru.
- Não criar parser mágico pra prosa de LLM; ajustar prompt, não topologia.
- Não deixar o curador aplicar mudança sem sombra+certificação.
- Não deixar run "barato/MVP" (gates/validadores soltos) entrar no corpus do curador/flywheel nem contar
  como evidência de versão — sempre marcado como não-certificado (V7).
- Não permitir composição entre casas sem contrato tipado na fronteira (vira prosa solta — V5/V7).
- **Não dar "ferramentas de auto-organização" (to-do/checklist que o nó marca) a um nó do grafo.** O
  organizador é o grafo; o nó é função pura. Dentro de uma run já existem: plano = WorkflowSpec, progresso
  = eventos, workspace = `runs/<id>/artefatos`, contexto/handoff = `deps_txt`. "Ver o progresso como
  checklist" é a **interface** lendo os eventos, não feature do kernel. O que ajuda o agente a entregar
  melhor é **retrieval** (camada de conhecimento/RAG/ferramentas), não auto-organização. **Estado mutável
  compartilhado entre nós é anti-padrão** — consistência se resolve por ordenação + evidência +
  reconciliação (Fase C), não por um "caderno" comum.

## Onde isto pode dar errado

- **Validador determinístico mal escrito** vira falso conforto (teste que não testa, schema frouxo). A
  catraca ajuda, mas validador também precisa de revisão.
- **Inchaço de escopo:** a gravidade das casas/control-plane vai puxar funcionalidade pra dentro do motor.
  Resistir é a decisão #5; quando em dúvida, fica fora.
- **Spec virando linguagem de programação.** Se a WorkflowSpec começar a precisar de lógica condicional
  rica demais, é sinal de que algo que devia ser nó/código virou dado. Reavaliar antes de crescer a DSL.
- **Evoluir sem run real.** Cada vetor estreia num uso real (Logisti/softwarehouse), não em abstrato —
  mesma regra de validação-primeiro de sempre.
