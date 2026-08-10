# LEIA-PRIMEIRO — Meta-fábrica

> **Para qualquer agente ou pessoa que chega aqui.** Este é o ponto de entrada. Leia este documento
> inteiro antes de mexer em qualquer coisa. Ele diz **o que estamos construindo, por quê, onde está, e
> como não ir na direção errada.** Os detalhes vivem nos documentos canônicos listados na §7.
>
> De: Caio (dono e arquiteto da visão) + revisão de arquitetura. Atualizado: 2026-08-10.
> Mantenha este documento vivo: quando a realidade mudar, atualize-o. Documento desatualizado mente.

---

## 1. O que é a meta-fábrica (em um parágrafo)

A meta-fábrica é um **simulador de organização**: recebe um objetivo ("construa o módulo X", "projete a
peça Y", "pesquise e sintetize Z") e **instancia o time de papéis especialistas** que o objetivo exige
(planner, arquiteto, engenheiros, QA, jurídico, designer, mantenedor…), rodando o **processo inteiro**
dentro de um motor + IA, com **gates e evidências**. Hoje entrega artefato intelectual (software, specs,
docs, design, patente); no futuro faz ponte com o físico. A missão tem **dois eixos inseparáveis**:
entregar **com maestria** (qualidade) e tornar o processo **cada vez mais seguro e barato** (eficiência).
A função-objetivo do sistema inteiro é **minimizar o tempo-até-decisão do humano e o retrabalho.**

**Software é a primeira vertical** — não por acaso: é onde a evidência é mais barata e rápida de verificar
(compila, testa, lint, SAST). É o melhor terreno pra provar as primitivas universais antes de generalizar
pra hardware, mecânica, jurídico, CAD.

A visão do dono, na metáfora dele: **uma fábrica/empresa de verdade, cheia de setores ("casas")** — a
softwarehouse, a hardwarehouse, a mechanical house — cada uma um harness de domínio cheio de agentes com
processo, entregando a sua parte com maestria, **pedindo coisas umas às outras** quando um projeto exige,
e o todo se organizando pra entregar. Um **curador** supervisiona: lê logs, mede, e ao longo do tempo
**cria especialistas** cada vez melhores e mais econômicos, bem alocados na fábrica.

---

## 2. A arquitetura em camadas (a decisão que organiza tudo)

A meta-fábrica é **fractal** e dividida em camadas. Confundir as camadas é o erro nº 1. Da mais profunda
à mais externa:

A **meta-fábrica é autossuficiente** — tem motor, casas E **interface própria**. Produtos externos
(Jarvis, Flint) podem *consumir* a meta-fábrica via MCP, mas ela **não depende de nenhum deles**.

```
  CONSUMIDORES EXTERNOS (opcionais, via MCP):
     Jarvis (assistente/porteiro)  ·  Flint (app de notas)  ·  outros clientes
        ▲  (MCP: despachar / status / stream de eventos)
  ┌─ META-FÁBRICA (autossuficiente) ─────────────────────────────────────────┐
  │  Interface própria      ── a superfície de 1ª classe: VÊ a fábrica rodando e
  │                            intercepta. Consome o stream de eventos do motor.
  │  Casas / harness         ── softwarehouse (dev-harness), hardware, mecânica… =
  │                            control-plane: org-chart, orçamento, coordenação.
  │  Motor (kernel)          ── roda UM processo (UM artefato) com maestria: grafo de
  │                            papéis, verificação adversarial, gate de cobertura, evidência.
  └────────────────────────────────────────────────────────────────────────────┘
```

A meta-fábrica tem **sua própria interface viva** (não depende de app externo pra ser vista/operada). O
**Jarvis** (assistente/porteiro) e o **Flint** (app de notas do dono) são **projetos separados** que
*podem se integrar* como clientes do mesmo stream MCP — a relação é unilateral: eles **usam** a
meta-fábrica; ela não usa nem depende deles.

**Regra pétrea (decisão #5, não relitigar): o motor é músculo, não autoridade.** Ele fabrica resultado
complexo e **expõe seu estado**. Ele **não** decide permissão, não classifica risco, não mede dinheiro,
não fala pelo dono. Toda autoridade mora **fora** dele (porteiro do Jarvis + MCPs especializados). O motor
roda *uma* casa fazendo *um* artefato; a **casa coordena muitas runs**; o **orquestrador coordena casas**.

**A meta-fábrica é fractal:** o mesmo padrão de prevenção que usamos *dentro* do motor (ordenar
dependências + handoff tipado com evidência + gate de cobertura) é o que vai valer *entre as casas*
(quando a hardwarehouse pedir algo à softwarehouse). Sem contrato tipado na fronteira, o pedido entre
casas vira "prosa solta" e reproduz, um nível acima, a mesma inconsistência que já resolvemos no nó.

---

## 3. Paperclip: a roda que NÃO vamos reinventar

O [Paperclip](https://github.com/paperclipai/paperclip) (MIT) é, em essência, a **camada de
empresa/control-plane** desta visão — consolidada e em produção, com a interface que o dono admirou. A
leitura honesta, nos dois sentidos:

- **Eles estão à frente no acabamento:** produto usável, interface, e o encanamento do control-plane já
  resolvido — orçamento/custo por company/agent/project/provider/model com hard-stops; taxonomia de
  eventos (activity, audit imutável, tracing de tool-call, OTel); governance & approvals (review/rollback);
  workspaces em git worktree; um survey de sistemas de memória (`doc/memory-landscape.md`).
- **Nós estamos à frente na parte difícil e profunda:** o **motor** (grafo de papéis com verificação
  adversarial + avaliador de cobertura + contrato de evidência + WorkflowSpec) é uma camada que eles não
  têm; o **curador/flywheel** de especialistas; o **rigor de "o que conta como pronto"**; e **multi-vertical**.
  Revelador: o roadmap *não-feito* deles (Memory/Knowledge, Enforced Outcomes, Organizational Learning,
  Deep Planning) é quase o mapa exato de onde o nosso design já vai mais fundo.

**A jogada (a tese de sempre): comprar a commodity, construir a diferenciação.** Reusar/estudar o
control-plane do Paperclip (custo, eventos, orçamento, approvals, UI) na **camada das casas** — nunca
dentro do motor — e despejar nosso tempo no **motor + curador**, que é onde somos de fato diferenciados.
Não estamos fazendo "o Paperclip 2". Estamos construindo a parte que eles ainda não chegaram, e pegando
emprestada a que eles já resolveram.

---

## 4. Princípios pétreos (as travas que mantêm a direção certa)

Toda decisão de desenvolvimento passa por estes filtros. Quem propuser algo que os viole está indo na
direção errada — pare e releia.

1. **Músculo, não autoridade.** O motor não decide permissão/risco/dinheiro/identidade. Gate sobe **cru**;
   classificação e cláusula pétrea moram no porteiro. (Ver `motor/docs/ARQUITETURA-MCP.md`.)
2. **A spec é a dinâmica; o grafo é fixo.** Feature nova = mudança na WorkflowSpec (dado), não nó novo no
   código. Padrão novo entra por **versão de spec certificada**, um de cada vez.
3. **Gate antes de flywheel.** Não dá pra afirmar "modelo pequeno ≈ grande" nem treinar com segurança sem
   um avaliador objetivo. **O gate é o grader.** A régua é o gargalo de tudo.
4. **Validação primeiro.** Nada vira método antes do primeiro uso real. **Logisti é a fornalha.** Cada
   capacidade nova estreia num uso real, não no abstrato.
5. **Conhecimento antes de peso — e verificador antes de conhecimento.** Boa parte da "maestria" vem
   de RAG + boas ferramentas + grafo de conhecimento — mais barato, sem treino, sem risco de
   collapse. Fine-tuning é o último recurso (os últimos 10%), só quando uma tarefa provar volume +
   estabilidade + grader confiável. **O gerador de hipótese (conhecimento público) é commodity que
   se compra; o seletor (verificação) é o que ninguém vende — e é onde o investimento rende.**
   Construir conhecimento próprio só onde a cegueira do gerador foi *medida*. Ver
   `DECISAO-conhecimento-e-julgamento.md` §2.
6. **Só dado gate-verificado treina (anti-collapse).** Flywheel que treina no próprio output cru degrada em
   silêncio. Mantenha âncoras de ouro pra detectar deriva.
7. **Imposto de complexidade.** Toda peça nova paga com ganho real em qualidade, custo ou segurança —
   senão fica no Later. O maior risco do projeto é **largura sobre profundidade** (cobrir tudo na
   superfície, dominar nada).
8. **Catálogo federado, não armazém.** O "universo conectado" de dados é ponteiros + metadados com
   proveniência/licença, não um banco gigante central. **Dado externo estocado é passivo, não
   ativo:** cada fonte ingerida é obrigação de frescor perpétua, e RAG vencido é pior que RAG
   nenhum — troca "não sei" por "sei errado". O ativo que compõe é o traço de execução com veredito,
   que a fábrica **produz**; não o documento que ela **estoca**.
9. **Primitivas nomeadas de forma agnóstica.** "reviewer", não "reviewer de código"; "evidência", não
   "teste" — pra outras verticais virarem config, não reescrita.
10. **Falsificável-primeiro, inerte-por-default.** Toda extensão entra atrás de flag/registro sem quebrar o
    que existe; cada passo tem um critério de falha claro e barato antes de virar fundação.
11. **Humano é input externo.** "Todo input externo é hostil até validado" vale para o fundador
    também. Achado de sênior, relatório de pentest e observação do dono entram como **hipótese com
    prior alto, não como veredito** — prior alto significa "testar primeiro", nunca "pular o teste".
    O humano é autoridade sobre **fins** (intenção, gosto, risco, dinheiro), não sobre **meios**:
    gate de correção sem verificador é sintoma de verificador faltando, não solução. Ver
    `DECISAO-conhecimento-e-julgamento.md` §3.
12. **Agnóstico sobre quem serve, nunca sobre saber quem serviu.** Liberdade total de provedor —
    assinaturas, créditos, free tier, GPU por segundo, tudo aproveitável. Mas rota carrega
    **atestação**: identidade verificável habilita julgar (verifier, curador, promoção); identidade
    só declarada serve para executar em volume, com evidência carimbada mais fraca. **Inferência se
    aluga** (há padrão de fato e o plugue já existe); **computação se constrói** (não há agregador
    que satisfaça a conformance de sandbox). Ver `DECISAO-provedores-e-computacao.md`.
13. **Spec rígida não é interface rígida.** O `WorkflowSpec` estrito é a qualidade do sistema;
    experiência engessada é defeito de UI, não requisito de disciplina. As duas coisas vivem em
    camadas diferentes e não se pagam mutuamente — a superfície pode ser inteiramente fluida e emitir
    spec rigorosamente validada. E vale a trava: **nada existe por estar no canvas; existe por estar
    no ledger ou numa spec.** Ver `DECISAO-canvas-e-operacao.md`.

---

## 5. Estado atual (fotografia honesta — 2026-08-07)

> **Cabeçalho:** motor **v0.5 em hardening T2 — não certificado para produção**. O programa H00–H13
> e a extensão H12b fecharam a maior parte dos achados da auditoria defensiva. Suíte na branch
> `refatoracao-painel`: **1121 passaram · 15 falharam · 35 pulados** (1171 coletados) — a branch
> **não está verde**; as 15 falhas são snapshot de pricing vencido no fixture e reprodutores de
> auditoria obsoletos, detalhados no `README.md`. Os três bloqueios de produção continuam abertos e
> são de ambiente/deployment, não de código faltando (ver `motor/docs/INVARIANTES.md`, "Dívidas
> conhecidas").

**O que JÁ funciona (validado em run real, não aspiracional):**

- **Motor v0.5** — grafo LangGraph fixo interpretando WorkflowSpec dinâmica. Padrão `fan_out_sintese` +
  rota `grafo_dependencias` (construção). Verificação adversarial por subagente, avaliador de cobertura,
  gate do fundador (`interrupt()`), jobs duráveis (SQLite checkpointer), telemetria JSONL.
- **Fase C completa** (loop de auto-correção) — os três pilares funcionando juntos: **prevenção** (rota de
  dependência em ondas: cada etapa vê a anterior), **escalada de tier** (subtarefa difícil reprovada sobe
  de degrau e converge), **reconciliação na fonte em loop bounded** (avaliador nomeia o nó culpado, motor
  re-dispara ele + dependentes até o gate aprovar ou bater o teto). Validado: `cobertura` indo de
  reprovado → **aprovado** em missão real.
- **Provider-agnóstico** — `ClienteOpenAICompat` (NVIDIA/Ollama/OpenRouter/Together/Groq, só muda
  `base_url`), `ClienteCodex`, `ClienteOpenCode`, `ClienteClaudeCLI`. Roteamento por papel/tier/pin/
  capacidade + **failover por custo** (`auto_esgotar`). Trocar de provedor = editar JSON, não reescrever.
- **Curador — fatia 3 landada** (a "sombra + certificação" que era aspiracional em julho): **observador**
  (telemetria → perfil), **telemetria por modelo**, **propositor por slot** (piso de qualidade, ciente de
  travas/timeouts), **livro-razão de custo**, e agora o rigor: **sombra read-only isolada por cópia
  profunda** (U1), **os dois lados medidos no mesmo runner** (U4), **certificação anti-Goodhart** que só
  aprova vantagem estatisticamente significativa (McNemar exato, p < 0.05, piso de 30 casos held-out)
  **e** custo médio estritamente menor (U2), **selo MAC com chave** — sem chave nada certifica (U5).
  **Promoção continua sendo só intenção `promocao_pendente` sujeita a gate humano** (U3/K4, ADR-003):
  sem `RepositorioCertificacoes` autoritativo, falha fechado. **Não há revogação** — certificação não
  tem prazo nem rebaixamento (ver `DECISAO-conhecimento-e-julgamento.md` §4).
- **Validadores determinísticos (V1)** — `schema_json`/`contem` como primitiva da spec (test/compile = nó ferramenta via subprocess): gate que
  passa/falha por **algoritmo**, não por opinião de LLM (o salto anti-alucinação, "Enforced Outcomes").
  Reprovação re-dispara o alvo via reconciliação.
- **Camada de conhecimento (RAG) — lift de RECUPERAÇÃO provado com régua honesta (v3, 2026-07-04)** —
  nó consome `fonte_rag`. A evidência v2 ("0/3→3/3") caiu no red-team item 3 (métrica tautológica +
  baseline ruído); o medidor v3 refez a régua com fatos não-adivinháveis, 3 braços e **execução isolada
  em tempdir** (o run dentro do repo contamina: o modelo lê os docs pelo filesystem): SEM RAG 1/5,
  RAG irrelevante 0/5, RAG relevante 5/5 — critério pré-registrado batido. Escopo honesto: prova
  **recuperação** numa config (codex/gpt-5.4-mini, n=5); **síntese** segue não medida (Frente C:
  números crus, sem veredito). "Conhecimento antes de peso" tem 1º sinal real agora. `LOG-VERIFICACAO.md`.
  **Ressalva registrada, não reaberta:** a Frente E rodou a mesma spec/modelo e deu 2/5 onde a B deu
  5/5 — o lift segue provado (coleta auditada da B), mas a **magnitude é instável entre harnesses**.
  Esse trio `1/5 · 0/5 · 5/5` mede **recuperação por RAG** e nada mais; não é número de durabilidade,
  de retomada nem de qualidade de entrega.
- **Eventos tipados + superfície MCP** — **63 eventos tipados** (`eventos_schema.py`, guard anti-drift)
  instrumentando tudo; `metafabrica.despachar_missao / status_missao / responder_gate / resumo_missao /
  eventos`, com input e resposta serializada limitados (64 KiB) e identidade de gate exposta.
  Ledger JSONL v2 append-only com writer único, `seq` contígua, recovery com quarentena.
- **Caixa do Fundador e livro-razão de orçamento** — decisão humana durável em SQLite com
  claim/lease/ack, replay, reserva exclusiva e recovery de crash; relay at-least-once para o ledger
  JSONL preservando `event_id` e deduplicando após reabertura. Todo efeito de modelo alcançável no
  grafo **reserva teto conservador antes do transporte**; custo desconhecido vira `UNKNOWN_COST` e
  bloqueia novas reservas.
- **Interface própria — construída** (era "em curso" em julho): painel React 19 + Vite sobre
  `painel.py`, ~20 telas (Dashboard, Grafo 2D/3D, Board, Runs, Caixa do Fundador, Custos, Curador,
  Datahouse, Nova Missão…), servindo projeções determinísticas do ledger. Contrato de honestidade
  operacional em `motor/specs/002-painel-operacional/spec.md`: nada de progresso, custo ou saúde
  simulados; controle ou faz a ação documentada ou fica visivelmente desabilitado.

**Em curso:** refatoração do painel (branch `refatoracao-painel`, 96 commits à frente do origin);
adapter OmniRoute custeado, buscando as duas rotas independentes que o preflight de topologia exige.

**Aspiracional (desenhado, ainda não construído):** fábrica de especialistas (fine-tuning/destilação
governados); **revogação de certificação** no curador; **calibração do gate humano** (medir se a
aprovação carrega informação); casas além da softwarehouse; ponte física. A **data-house** permanece
condicionada: o lift de *recuperação* foi provado numa config única (n=5) e com magnitude instável
entre harnesses — e a `DECISAO-conhecimento-e-julgamento.md` reordena o problema (executar →
ler o instalado → buscar ao vivo → só então cachear). Ver §6 e o ROADMAP.

**Projetos SEPARADOS que consomem a meta-fábrica (não fazem parte dela, não são dependência):**
**Jarvis** (assistente local; consome a meta-fábrica como motor headless), **Flint** (app de notas do
dono; pode *integrar* a meta-fábrica como cliente externo opcional — a meta-fábrica não depende dele).
**Fazem parte do núcleo (este repo):** **dev-harness** (a softwarehouse: metodologia de engenharia),
**harness-hardware / harness-mecanico** (sementes das próximas verticais).

---

## 6. O norte (para onde vamos)

Resumo; o detalhe Now/Next/Later está no `ROADMAP.md`.

- **Curto (o que destrava tudo):** **certificar um backend de sandbox** contra
  `motor/specs/001-hardening-producao/sandbox-conformance.md`. É o bloqueio nº 1 e é o único
  verificador barato de verdade que temos — enquanto o motor não roda o que escreve, "garantia de
  entrega" é afirmação não-verificável e a alça experiência→conhecimento não fecha. `CommandRunner`
  já é um `Protocol`: o caminho mais curto pode não ser um runner Linux dedicado, e sim um backend
  de nuvem com container isolado, imagem por digest e cobrança por segundo (**Modal** é o candidato
  óbvio, e a mesma primitiva serve depois ao fine-tuning do V6). Pré-requisito: ler a conformance
  contra a doc do provedor **antes** de codar — egress, limite de output por streaming e cleanup
  determinístico decidem. Em paralelo: **duas rotas de provedor independentes e custeadas**
  (bloqueio nº 2 — hoje todos os papéis passam pelo mesmo proxy, ver dívida 8) e **rodar a primeira
  missão real ponta a ponta** — não para entregar produto, para medir onde o processo vaza.
  *(Interface viva, eventos tipados e validadores determinísticos: **feitos**. Detalhe do ciclo de
  vida do workflow em `DECISAO-ciclo-de-vida-workflow.md`.)*
- **Interface (paralelo, não concorrente ao Curto):** a superfície de operação vira **canvas infinito
  por andares** com **andon** — o sinal de defeito leva o operador à estação exata, e o curador aprende
  para não repetir. Dois itens valem mesmo sem canvas nenhum e vêm primeiro: **streaming incremental
  sobre `seq`** (com detecção de buraco) e **coordenada de estação nos eventos de falha**. Depois:
  vista → zona de rascunho sem autoridade → autoria emitindo spec → casca com notificação nativa. Ver
  `DECISAO-canvas-e-operacao.md`.
- **Médio:** fechar a alça do curador — **`RepositorioCertificacoes` autoritativo** (bloqueio nº 3) é
  o que faz processo que deu certo virar conhecimento reutilizável; é o "data" que a tese realmente
  pede, e vem acompanhado de **revogação** (certificação sem prazo vira tradição, não conhecimento).
  Junto: **calibrar o gate humano** — tratar aprovação como predição e medir poder discriminante, o
  detector empírico de "gate cerimonial". Spec-kit rodando no Logisti (validação real); semente da
  camada de conhecimento só onde a cegueira do gerador for medida (princípio 5).
- **Longo (a fábrica de especialistas):** o curador como supervisor que **cria monstrinhos** — modelos
  pequenos, baratos, super-especializados por papel (backend, CAD…), via RAG + ferramentas primeiro e
  fine-tuning/destilação depois. **Disciplina inegociável:** (a) a régua/grader vem antes — rollout
  vertical por vertical, ordenado por **quão barato é o grader** (software cedo, CAD muito depois); (b)
  **treinar um especialista é, ele mesmo, uma run gated do motor** (coleta sob gates de licença →
  fine-tune → **eval no held-out como nó validador** → só promove se bater o titular em qualidade **e**
  custo); (c) **coleta massiva de dados é uma "data-house" separada** — o curador decide *o que* falta
  (gap map) e avalia; não vira o scraper; (d) **a fábrica se constrói a si mesma** usando a própria máquina
  gated; (e) o **livro-razão de custo** é o que torna "vale a pena treinar este especialista?" uma conta de
  ROI, não um hobby; (f) **proveniência no treino**: todo especialista carrega que dado/modelo/versão o
  produziu.
- **Guarda permanente:** as casas/control-plane ficam **ACIMA** do motor (reusar Paperclip lá, nunca
  inchar o kernel).

**Sequência honesta:** prove **UM** especialista ponta a ponta na vertical de grader mais barato (software)
— um backend que bate o generalista em custo e passa no gate em tarefa real, com o loop
treina→avalia→aloca→monitora→re-treina fechado e gate-seguro. *Esse* run prova o flywheel. Só então replica.
Antes disso, casa nova e especialista de CAD são fé, não engenharia.

---

## 7. Mapa dos documentos canônicos (ordem de leitura)

Leia nesta ordem para entender o sistema:

1. **`docs/LEIA-PRIMEIRO.md`** (este) — a visão, as camadas, os princípios, o estado, o norte.
2. **`docs/ROADMAP.md`** — o mapa operacional Now/Next/Later de todo o sistema (qual pilar, em que
   ordem). É onde se decide o que vem a seguir.
3. **`docs/design/interface-briefing.md`** — a visão completa da interface viva **própria da meta-fábrica**, com
   status de maturidade de cada capacidade. O "como o dono quer ver a fábrica".
4. **`motor/docs/EVOLUCAO.md`** — o norte do **motor**: os vetores aditivos (validadores
   determinísticos, eventos tipados, curador-catraca, spec v0.2, fronteira fractal, fábrica de
   especialistas). Regra de ouro: melhorar, não substituir.
4b. **`docs/DECISAO-ciclo-de-vida-workflow.md`** — como um workflow nasce, é personalizado,
   **versionado com evidência**, executado (inclusive **parcialmente / modo MVP**), **composto
   entre casas** e melhorado pelo curador. Autoria de workflow **é uma run do motor**; catálogo de
   templates; o guardrail "melhor/pior é dado, não opinião". Canônico no tema workflow.
4c. **`docs/DECISAO-conhecimento-e-julgamento.md`** — onde entra dado e onde entra humano. Por que o
   gerador de hipótese se compra e o seletor se constrói; a ordem executar → ler o instalado →
   buscar ao vivo → cachear; o gate tipado pela **pergunta** (autoridade / fim / gosto / correção) e
   não só pelo risco; humano como input externo (hipótese, não veredito); revogação de certificação.
   Canônico no tema conhecimento e julgamento.
4d. **`docs/DECISAO-provedores-e-computacao.md`** — quem serve o poder de processamento. Inferência
   se aluga (padrão de fato, plugue já existe); computação se constrói (`CommandRunner` plugável,
   backend de nuvem como candidato ao bloqueio nº 1, e a mesma primitiva serve ao fine-tuning);
   capacidade estendida de "o que o modelo sabe" para "o que a rota executa"; atestação de rota —
   verificável julga, declarada só executa. Canônico no tema provedor, roteamento e execução.
4e. **`docs/DECISAO-canvas-e-operacao.md`** — a superfície de operação: canvas infinito por andares,
   o **andon** (o sinal leva você à estação exata do defeito), zona de rascunho sem autoridade vs.
   zona de roteiro que emite `WorkflowSpec`, streaming incremental sobre `seq`, LOD e a escolha de
   casca. Canônico no tema interface de operação, junto com
   `../motor/specs/002-painel-operacional/spec.md`.
4f. **`docs/DECISAO-manutencao-e-custodia.md`** — o que acontece depois da entrega. O **dossiê**
   (contexto durável sobre um sujeito, com carimbo de evidência por entrada — o mecanismo geral de dar
   contexto a agente); gatilho invertido (evento do mundo, não objetivo humano); a escada
   **mitigar → corrigir → causa raiz**; autonomia por reversibilidade; o flywheel de segurança, cujo
   grader é quase de graça; e o risco de monocultura na carteira. Canônico no tema manutenção.
5. **`motor/docs/ARQUITETURA-MCP.md`** — a **fronteira**: como o motor vira MCP, e a linha entre
   o que o motor faz e o que o porteiro/orquestrador faz. Decisões travadas.
6. **`motor/README.md`** — entrada técnica do motor (como rodar, testar, Studio).
7. **`dev-harness/`** — a softwarehouse: metodologia de engenharia (PLAYBOOK, spec-kit, tiers T0/T1/T2,
   security-DoD, `docs/biblioteca-de-validadores.md`, fases). É a primeira "casa".

**Onde vivem os briefings (regra: spec/visão no monorepo; preparo-de-implementação no repo do produto):**
o `docs/design/interface-briefing.md` (a *spec* da **interface própria da meta-fábrica**) fica **aqui** no
monorepo, canônico — é o que guia a construção da nossa interface; clientes externos (Flint) podem
referenciá-la se quiserem integrar. Os briefings de *terreno de produto* vivem nos repos dos produtos
externos: **Flint** tem o `BRIEFING-FLINT-superficie-meta-fabrica.md` (como o Flint *consome* a
meta-fábrica: cliente MCP, ingestão de eventos, canvas); **Jarvis** tem o
`BRIEFING-JARVIS-orquestrador-meta-fabrica.md` (papel de porteiro/orquestrador, consumo do motor). O
contrato MCP que esses clientes consomem é canônico e fica no monorepo (`motor/docs/ARQUITETURA-MCP.md`).

Visão e kernel canônicos de longo prazo vivem no **vault Obsidian** (`2. Pessoal/Meta-fábrica*.md`); estes
documentos são o mapa operacional versionado.

---

## 8. Como trabalhamos (o regime, para os agentes)

- **Divisão de papéis:** Claude (sessões Cowork) = **arquiteta + verifica** — desenha, escreve **HANDOFFs
  travados**, e audita cada entrega (diff + testes + sondagem independente). Codex (no Mac) = **executa** um
  handoff/commit por vez. A verificação cross-model é proposital (anti-viés de auto-preferência).
- **Handoffs** (`motor/HANDOFF-CODEX-*.md`) são o contrato de trabalho: objetivo, mudanças precisas,
  restrições (inerte-por-default), e **critérios de falsificação (DoD)**. Podem ser **encadeados** (vários
  PRs em ordem) quando os passos são independentes e seguros.
- **Inerte-por-default:** toda extensão entra atrás de flag/registro/versão sem quebrar a suíte existente.
- **Falsificável-primeiro:** antes de construir, defina como saberíamos que falhou; prefira o teste barato
  primeiro. Rodar em uso real (Logisti) é o juiz final.
- **Onde isto pode dar errado:** todo documento e handoff termina com um bloco honesto de riscos. Cultura
  anti-bajulação: a régua é a evidência, não a opinião.

---

## 9. Onde isto pode dar errado (os riscos de direção)

- **Largura sobre profundidade** — o maior risco. Cobrir dez casas/pilares na superfície e não dominar
  nenhum. Os pilares do Later existem pra não perder a ideia *e* pra não começá-la cedo demais.
- **Inchar o motor** — a gravidade do control-plane (orçamento, org-chart, permissão) vai puxar
  funcionalidade pra dentro do kernel. Resistir é a decisão #5; em dúvida, fica fora (na casa).
- **Flywheel sem grader** — treinar/auto-melhorar sem avaliador objetivo é afiar faca no escuro; degrada em
  silêncio. Gate antes de flywheel, sempre.
- **Interface antes do sinal** — não se visualiza uma fábrica que não emite eventos. O esquema de eventos
  vem antes da tela bonita.
- **Centralizar dado cedo** — catálogo federado, não armazém.
- **Independência que só existe na config** — dois `route_id` distintos atrás do mesmo agregador é
  independência **declarada**, não observada. Auto-fallback, que é a feature de vitrine desse tipo
  de gateway, faria executor e verifier caírem no mesmo upstream em silêncio, e o motor registraria
  dois julgamentos onde houve um. Atestação por resposta ou um papel fora do proxy.
- **Reimplementar transporte** — cliente para N provedores de inferência é commodity com padrão de
  fato; o esforço rende em execução atestada (sandbox, capacidade de computação), não em gateway.
- **Fundação sobre crédito promocional** — GPU barata por crédito que expira é hipoteca. A
  abstração precisa aguentar o provedor sair.
- **Reinventar o control-plane** — o Paperclip (MIT) já resolveu o encanamento; copiá-lo/reusá-lo libera
  tempo pro que é nosso diferencial.
- **Reinventar organização que o grafo já dá** — dar checklist/to-do a um nó do motor duplica o grafo (que
  é o organizador) e empurra a spec a virar programa. Dentro de uma run, plano = WorkflowSpec, progresso =
  eventos, workspace = `runs/<id>`, contexto = `deps_txt` já existem; "ver o progresso" é a interface;
  melhorar a *entrega* do agente é **retrieval** (camada de conhecimento, Next #4), não auto-organização.
  Estado mutável compartilhado entre nós é anti-padrão (consistência = ordenação + evidência +
  reconciliação, não "caderno" comum).
- **Não substitui julgamento** — os gates pegam o conhecido. Escala nova e fluxo que toca dinheiro/dado
  pessoal ainda exigem um humano olhando.
- **Gate humano que carimba sem ler** — o modo de falha mais silencioso. Fora da sua faixa de
  competência o humano não devolve silêncio: devolve **ruído com selo de aprovação**, e uma
  reprovação legítima carimbada como "aprovado" entra no catálogo como processo que funciona. É
  contaminação do ativo composto, não só gate inútil. Duas defesas: perguntar só o que é respondível
  dentro da competência e do orçamento de atenção do humano, e **medir** se a aprovação carrega
  informação.
- **Gate humano satura** — se a fábrica gerar cem intenções por dia, o humano carimba sem ler e a
  autoridade migra *de fato* para a máquina sem migrar *de direito*. Escalar produção sem escalar
  julgamento é o modo de falha estrutural da regra pétrea, e ele não aparece em teste nenhum.
- **Certificação sem prazo fossiliza** — conhecimento consolidado também carrega prática que
  funcionou pelo motivo errado e regra cujo contexto evaporou. Sem revogação, a fábrica de processo
  vira burocracia por acumulação: o risco "gate cerimonial" um nível acima.
- **Documento desatualizado mente** — este arquivo passou ~5 semanas afirmando "suíte ~244 verde",
  "48 eventos" e "curador fatia 3 aspiracional" quando os três já eram falsos. Número em documento
  narrativo apodrece; a matriz de invariantes e os testes têm precedência.
