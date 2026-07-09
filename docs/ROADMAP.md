# ROADMAP — Meta-fábrica

> A camada **acima** dos roadmaps de cada projeto (dev-harness, motor, Jarvis, Flint) e da
> [Fase 4](dev-harness/fase4-roadmap-ciclo-de-vida.md). Aqui se decide *quais pilares, em que ordem*,
> no sistema inteiro. Formato **Now / Next / Later** por horizonte, não por data (data vira mentira).
> Vive na raiz, versionado. Atualize quando a realidade mudar — é esperado, não falha.
>
> Síntese das conversas de planejamento de 2026-06-29. Visão e kernel canônicos: vault Obsidian
> (`2. Pessoal/Meta-fábrica*.md`). Este arquivo é o mapa operacional, não a visão.

---

## A essência em uma frase

A meta-fábrica é um **simulador de organização**: recebe um objetivo, instancia o time de papéis
especialistas que ele exige (engenheiros, arquiteto, jurídico, designer, QA, mantenedor…) e roda o
processo inteiro dentro de um motor + IA, com gates e evidências. Hoje produz **artefato intelectual**
(software, specs, docs, design, patente); no futuro faz ponte com o físico. **Software é a primeira
vertical** — não por acaso: é onde a evidência é mais barata e rápida de verificar (CI, testes), logo
o melhor terreno pra provar as primitivas universais antes de generalizar.

Missão, em dois eixos: **entregar coisa boa** (qualidade) e **processo cada vez mais seguro e barato**.
Função-objetivo do sistema: **minimizar o tempo-até-decisão do humano e o retrabalho.**

## Paperclip — a roda emprestada (não reinventar o control-plane)

O [Paperclip](https://github.com/paperclipai/paperclip) (MIT) é a **camada de empresa/control-plane**
desta visão, já consolidada e em produção. Eles estão à frente no **acabamento** (produto usável,
interface, orçamento/custo com hard-stops, taxonomia de eventos/audit/OTel, governance & approvals,
worktrees, survey de memória). **Nós estamos à frente na profundidade**: o motor (grafo de papéis +
verificação adversarial + gate de cobertura + contrato de evidência) não existe lá; o curador/flywheel e
o rigor de "o que conta como pronto" também não — e o roadmap *não-feito* deles é quase o nosso mapa.

**Decisão:** comprar a commodity, construir a diferenciação. Reusar/estudar o control-plane do Paperclip
na **camada das casas** (nunca dentro do motor — decisão #5) e concentrar nosso esforço no **motor +
curador**. Detalhe em `LEIA-PRIMEIRO.md` §3.

## Estado atual (uma fotografia honesta)

- **motor v0.5** — grafo LangGraph fixo interpretando WorkflowSpec dinâmica; padrão fan-out-and-
  synthesize + rota `grafo_dependencias` (construção). Verificação adversarial por subagente, avaliador
  de cobertura, **gate do fundador** (`interrupt()`), jobs duráveis (SQLite). Provider-agnóstico
  (OpenAI-compat/Codex/OpenCode/claude; roteamento papel/tier/pin/capacidade + failover por custo).
  Suíte ~262+ verde. **Fase C COMPLETA** (loop de auto-correção): prevenção (rota de dependência em
  ondas) + escalada de tier (subtarefa difícil sobe de degrau e converge) + reconciliação na fonte em
  loop bounded (avaliador nomeia o nó culpado → re-dispara ele + dependentes até aprovar/teto). Validado
  em run real (`cobertura` reprovado→aprovado).
- **Curador — FUNDAÇÃO COMPLETA** (read-only): observador + telemetria-por-modelo + propositor por slot
  (ranqueia modelo por papel/tier, com piso de qualidade, ciente de travas/timeouts, **usando custo_usd
  real no desempate**) + **livro-razão de custo** (tokens+tempo+$). O cérebro de medição e alocação. Falta
  a fatia 3 (ele *agir*: sombra + certificação).
- **Eventos + V1 FEITOS:** **48 eventos tipados** (`eventos_schema.py`, guard anti-drift) + superfície MCP
  (`despachar/status/responder_gate/resumo/eventos`); **validadores determinísticos V1** (`schema_json`/
  `contem`); **RAG com lift de recuperação provado** (0/3→3/3 por métrica de substring — prova recuperação, não síntese). Ver `LOG-VERIFICACAO.md`.
- **Ciclo de vida do workflow — DECIDIDO** (doc `DECISAO-ciclo-de-vida-workflow.md`): catálogo de templates
  versionados, autoria-como-run, versionamento com evidência, execução parcial/MVP (run não-certificado
  fora do flywheel), composição entre casas com contrato tipado. Construção da UI/registro é Now/Next.
- **dev-harness** — metodologia madura (FIC, tiers T0/T1/T2, DoD, anti-bajulação, security-DoD,
  spec-kit decidido). **Lacuna principal:** o gate ainda é auto-reportado pelo agente; o CI mecânico
  que bloqueia merge (Fase 4, passo 1) ainda não foi fiado. Estreia prevista no Logisti.
- **Jarvis v0.1** — assistente local (Ollama/Qwen, voz, memória em duas camadas, MCP). Consome a
  meta-fábrica como motor headless.
- **Flint** — app de notas do dono (substituto do Obsidian); **projeto separado** que *pode* integrar a
  meta-fábrica como **cliente externo opcional** (não é a superfície dela — a meta-fábrica tem interface
  própria; e ela não depende do Flint). Hoje é visão+v1.
- **Verticais não-software já germinando:** pastas `harness-hardware/` e `harness-mecanico/` com
  blueprint e constituição — sementes das próximas verticais.

## Os pilares, mapeados à missão

| Pilar | Eixo | Onde está |
|---|---|---|
| Processo / gates de evidência | boa + segura | dev-harness forte; Fase C completa no motor; gate CI externo pendente (Fase 4 p1) |
| Auto-evolução (curador / flywheel) | segura + barata | **fundação read-only completa** (observador+propositor+custo); falta fatia 3 (agir: sombra+certificação) |
| Eficiência (modelos pequenos especialistas) | barata | telemetria-por-modelo **feita** (perfil de aptidão por slot); fábrica de especialistas é Later |
| Camada de dados / conhecimento | boa | só a semente md (memória/Obsidian); grafo de conhecimento é Next |
| Custo (medição) | barata | **livro-razão feito** (tokens+tempo+$ **estimado**: tabela manual, sem reconciliação vs fatura — item 15); propositor usa custo_usd no desempate |
| Interface viva (própria da meta-fábrica) | tempo-até-decisão | briefing v2 completo (board + editor de workflow); **48 eventos tipados feitos**; construção da UI é o Now |
| Ciclo de vida do workflow | boa + barata | **decidido** (catálogo, versão-com-evidência, autoria-como-run, execução parcial/MVP) — ver `DECISAO-ciclo-de-vida-workflow.md` |

---

## Now (o próximo tijolo — máx 1-2 frentes de cada vez)

> Tudo aqui converge num só ponto: **a infraestrutura de evidência/avaliação.** Gate, telemetria,
> dataset de treino e interface são quatro ângulos da mesma fundação. Construí-la primeiro destrava
> o resto.

- [x] **Curador fatias 1-2 + telemetria-por-modelo + livro-razão de custo** — FEITO (read-only,
  determinístico). Fundação do flywheel *e* da medição de aptidão/custo por (papel, tier, modelo). ✅
- [x] **Esquema de eventos motor→superfície** — FEITO. 48 eventos tipados + guard anti-drift + superfície
  MCP. É o gancho da interface viva e o ponto de interceptação; instrumenta tudo. ✅
- [x] **Validadores determinísticos como primitiva da spec** (motor V1) — FEITO. A WorkflowSpec declara nós
  validadores (`schema_json`/`contem`; test/compile = nó ferramenta); reprovação re-dispara via reconciliação. RAG com lift
  provado por essa métrica. ✅
- [ ] **Interface viva — P0** (board de missões + Grafo 2D com editor de workflow + Caixa do Fundador).
  Construída sobre os eventos já emitidos. Ver `design/BRIEF-DESIGN-interface-meta-fabrica.md` e
  `DECISAO-ciclo-de-vida-workflow.md`.
- [ ] **Gate externo de CI** (Fase 4, passo 1) — T1. A máquina bloqueia merge (lint · type · test ·
  SAST · secrets · build); o agente propõe, a máquina decide. **Estreia no Logisti.** É o tijolo que
  tira o gate da mão do agente.

## Next (entra quando o Now esvaziar — ordenado por valor × risco)

1. ~~**Livro-razão de custo** + **propositor usa custo_usd real**~~ — FEITO ✅ (tokens+tempo+$ por
   run/modelo; desempate por $/chamada real).
2. **Catálogo de workflows + versionamento com evidência + autoria-como-run** — o registro de templates
   versionados (metadados "quando usar"); criar workflow novo = uma run do motor (pesquisa→síntese→spec);
   cada versão carrega sua telemetria (certificação = versão + evidência). Ver
   `DECISAO-ciclo-de-vida-workflow.md`. Casa com o editor de workflow da interface.
3. **Curador fatia 3** — teste em sombra + certificação antes de aplicar qualquer mudança de catálogo.
   **É também o guardrail do "melhor/pior é dado, não opinião"** na edição de workflow (o agente suspeita;
   a sombra decide).
   O ponto onde a auto-evolução começa a *agir*, com trava. **Timing:** casa com a troca de provedor do
   Caio (Codex→Ollama/OpenRouter) — é o cenário exato de "testar um modelo novo antes de confiar".
4. **spec-kit + constituição rodando no Logisti** — decisão já tomada; falta o estresse real.
5. **Semente da camada de conhecimento** — grafo md dos próprios outputs/decisões do harness, com
   **proveniência + confiança + licença em cada nó**. Dobra como visão de aprendizado (Obsidian/Flint),
   fonte de recuperação pro agente e semente de dataset. Custa quase nada hoje.
   - **Ontologia emergente, não desenhada na frente.** O schema do grafo cresce do uso real; tentar
     projetar a ontologia universal antes mata o projeto (é como grafos de conhecimento morrem). Comece
     pelo *teu* grafo (projetos, decisões, runs) e só depois ingira o externo.
   - **Gap map** — registrar também o que o agente *tentou usar e não achou*. O negativo do grafo é tão
     valioso quanto o positivo: é ele que dá norte ao que coletar/ingerir e à estratégia de consumo de
     dados pro treino. É o que o curador opera.
6. **NFRs na spec + estratégia de testes** (Fase 4, passos 2-3) — escala como requisito a montante.

> O **esquema de eventos motor→superfície** já saiu daqui e do Now — está **FEITO** (48 eventos tipados
> incluindo `aresta.fluxo`, `custo.tick`, `artefato.atualizou`, `validador.rodou`). O próximo consumidor
> desses eventos é a interface viva (Now).

## Later (capturado, não comprometido — começar cedo demais é o risco)

- **Loop de produção + learn-time** (Fase 4, passos 4-5) — quando houver produção real com usuários.
- **Interface viva própria da meta-fábrica** — começa *read-only* visualizando o stream de eventos; depois
  zoom semântico (macro→micro), interceptação (observar/sugerir/parar/assumir) e replay. Depende do motor
  emitir eventos e rodar projetos multiagente. (Clientes externos como o Flint podem consumir o mesmo
  stream, opcionalmente.) Ver `design/interface-briefing.md`.
- **Fábrica de especialistas (a visão do curador-supervisor)** — o curador cria "monstrinhos": modelos
  pequenos, baratos, super-especializados por papel (backend, CAD…) que entregam com maestria. Disciplina
  inegociável (senão é hobby perigoso): **(a)** a régua vem antes — rollout vertical por vertical,
  ordenado por **quão barato é o grader** (software cedo; CAD/jurídico muito depois); **(b)** preferir
  **conhecimento a peso** — RAG + ferramentas + grafo primeiro; fine-tuning/destilação só quando a tarefa
  provar volume + estabilidade + grader confiável; **(c)** **treinar um especialista é uma run gated do
  motor** — coleta sob gates de licença → fine-tune → eval no held-out como **nó validador** → só promove
  se bater o titular em qualidade **e** custo; **(d)** **coleta massiva = "data-house" separada** (o
  curador decide *o que* falta via gap map e avalia; não vira o scraper); **(e)** a fábrica **se constrói
  a si mesma** com a própria máquina gated; **(f)** **livro-razão de custo** torna "vale treinar?" uma
  conta de ROI; **(g)** **proveniência no treino** (todo especialista carrega que dado/modelo/versão o
  produziu). **Trava anti-collapse: só dado gate-verificado (ou humano) vira sinal de treino**; âncoras de
  ouro detectam deriva. **Sequência:** prove UM especialista (backend) ponta a ponta antes de generalizar.
- **Camada de dados federada** — catálogo (ponteiros + metadados) sobre Cloudflare/HuggingFace/Postgres;
  ingestão externa governada (datasheets, livros) com os mesmos gates de IP/licença. Catálogo, não
  armazém.
- **Conhecimento institucional entre projetos** — o ativo que compõe: decisões, padrões e modos de falha
  de um projeto ficam recuperáveis pro próximo (o drone nº2 reaproveita o nº1). É distinto de peso de
  modelo — é conhecimento, não treino — e faz a organização ficar melhor sem treinar nada. Reprodutibilidade
  anda junto: todo artefato sabe qual modelo/versão o produziu (já semeado nos eventos `modelo.roteado`).
- **Novas verticais (domain packs)** — hardware, mecânico, jurídico, CAD. Ordem decidida por **quão
  barato e objetivo é o grader do domínio** (Verilog/código antes; CAD/jurídico muito depois).
- **Ponte física** — sim-to-real, controle por RL (ex.: IA que pilota drone). Paradigma de ML diferente
  do fine-tuning de LLM; horizonte longo, muita validação.

---

## Princípios de sequenciamento

1. **Software primeiro, ponta-a-ponta.** Uma vertical sólida vale mais que dez pela metade. É onde o
   grader é barato — prove as primitivas aqui.
2. **Primitivas nomeadas de forma agnóstica.** Não "reviewer de código" e sim "reviewer"; não "teste"
   e sim "evidência" — pra hardware/jurídico depois serem config, não reescrita.
3. **Gate antes de flywheel.** Não dá pra afirmar "modelo pequeno ≈ grande", nem treinar com segurança,
   sem o avaliador objetivo. O gate é o grader.
4. **Colher dado agora, treinar depois.** Logar `spec→plano→código→evidência→correção` é de graça e
   semeia o dataset ouro; fine-tuning espera o volume justificar.
5. **Imposto de complexidade.** Toda peça nova paga com ganho real em qualidade, custo ou segurança —
   senão fica no Later.
6. **Validação primeiro.** Nada vira método antes do primeiro uso real (Logisti é a fornalha).

## Onde isto pode dar errado

- **Largura sobre profundidade.** O maior risco não é faltar pilar — é cobrir todos na superfície e
  não dominar nenhum. Os pilares do Later existem pra não se perder a ideia *e* pra não começá-la cedo.
- **Gate teatral.** CI lento/flaky o time aprende a burlar (`--no-verify`). Rápido (<5 min) e
  determinístico, ou é pior que não ter.
- **Model collapse.** Flywheel que treina no próprio output cru degrada em silêncio. Só dado
  gate-verificado treina; mantenha âncoras de ouro pra detectar deriva.
- **Centralizar dado cedo.** O "universo conectado" realista é catálogo federado, não um banco gigante.
- **Interface antes do sinal.** Não se visualiza uma fábrica que não emite eventos. O esquema de
  eventos vem antes da tela bonita.
- **Não substitui julgamento.** Os gates pegam o conhecido. Escala nova e fluxo que toca dinheiro/dado
  pessoal ainda exigem um humano olhando.
