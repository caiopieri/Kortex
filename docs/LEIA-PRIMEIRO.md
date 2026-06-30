# LEIA-PRIMEIRO — Meta-fábrica

> **Para qualquer agente ou pessoa que chega aqui.** Este é o ponto de entrada. Leia este documento
> inteiro antes de mexer em qualquer coisa. Ele diz **o que estamos construindo, por quê, onde está, e
> como não ir na direção errada.** Os detalhes vivem nos documentos canônicos listados na §7.
>
> De: Caio (dono e arquiteto da visão) + revisão de arquitetura. Atualizado: 2026-06-29.
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

```
  Flint (superfície / cliente)         ── VÊ a fábrica rodando; intercepta sem parar. Headless engine ≠ UI.
        ▲  (MCP, stream de eventos)
  Orquestrador / Porteiro (Jarvis)     ── entende intenção, roteia, GUARDA (risco, dinheiro, identidade).
        ▲  (MCP fino)
  Casas / Harness de domínio           ── softwarehouse (dev-harness), hardwarehouse, mechanical house…
        │   = CONTROL-PLANE: org-chart, orçamento, tickets, coordenação entre papéis/casas.
        ▲
  Motor (kernel / meta-fábrica)        ── roda UM processo (UM artefato) com maestria: grafo de papéis,
                                          verificação adversarial, gate de cobertura, contrato de evidência.
```

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
5. **Conhecimento antes de peso.** Boa parte da "maestria" vem de RAG + boas ferramentas + grafo de
   conhecimento — mais barato, sem treino, sem risco de collapse. Fine-tuning é o último recurso (os
   últimos 10%), só quando uma tarefa provar volume + estabilidade + grader confiável.
6. **Só dado gate-verificado treina (anti-collapse).** Flywheel que treina no próprio output cru degrada em
   silêncio. Mantenha âncoras de ouro pra detectar deriva.
7. **Imposto de complexidade.** Toda peça nova paga com ganho real em qualidade, custo ou segurança —
   senão fica no Later. O maior risco do projeto é **largura sobre profundidade** (cobrir tudo na
   superfície, dominar nada).
8. **Catálogo federado, não armazém.** O "universo conectado" de dados é ponteiros + metadados com
   proveniência/licença, não um banco gigante central.
9. **Primitivas nomeadas de forma agnóstica.** "reviewer", não "reviewer de código"; "evidência", não
   "teste" — pra outras verticais virarem config, não reescrita.
10. **Falsificável-primeiro, inerte-por-default.** Toda extensão entra atrás de flag/registro sem quebrar o
    que existe; cada passo tem um critério de falha claro e barato antes de virar fundação.

---

## 5. Estado atual (fotografia honesta — 2026-06-29)

**O que JÁ funciona (validado em run real, não aspiracional):**

- **Motor v0.5** — grafo LangGraph fixo interpretando WorkflowSpec dinâmica. Padrão `fan_out_sintese` +
  rota `grafo_dependencias` (construção). Verificação adversarial por subagente, avaliador de cobertura,
  gate do fundador (`interrupt()`), jobs duráveis (SQLite checkpointer), telemetria JSONL. Suíte ~244 verde.
- **Fase C completa** (loop de auto-correção) — os três pilares funcionando juntos: **prevenção** (rota de
  dependência em ondas: cada etapa vê a anterior), **escalada de tier** (subtarefa difícil reprovada sobe
  de degrau e converge), **reconciliação na fonte em loop bounded** (avaliador nomeia o nó culpado, motor
  re-dispara ele + dependentes até o gate aprovar ou bater o teto). Validado: `cobertura` indo de
  reprovado → **aprovado** em missão real.
- **Provider-agnóstico** — `ClienteOpenAICompat` (NVIDIA/Ollama/OpenRouter/Together/Groq, só muda
  `base_url`), `ClienteCodex`, `ClienteOpenCode`, `ClienteClaudeCLI`. Roteamento por papel/tier/pin/
  capacidade + **failover por custo** (`auto_esgotar`). Trocar de provedor = editar JSON, não reescrever.
- **Curador — fundação completa** (read-only): **observador** (telemetria → perfil), **telemetria por
  modelo**, **propositor por slot** (ranqueia modelo por papel/tier, com **piso de qualidade** e ciente de
  **travas/timeouts** — não recomenda modelo que trava nem fraco demais), e **livro-razão de custo**
  (tokens + tempo + $ via tabela de preço). É o cérebro de medição e alocação.
- **Superfície MCP fina** — `metafabrica.despachar_missao / status_missao / responder_gate / resumo_missao`.

**Em curso:** esquema de eventos motor→superfície tipado + canal de stream (handoff escrito; é o gancho da
interface viva).

**Aspiracional (desenhado, ainda não construído):** interface viva (Flint); curador que **age** (fatia 3:
sombra + certificação); fábrica de especialistas (fine-tuning/destilação governados); casas além da
softwarehouse; ponte física. Ver §6 e o ROADMAP.

**Outros projetos do ecossistema:** **Jarvis** (assistente local; consome a meta-fábrica como motor
headless), **Flint** (app de notas; a superfície/cliente), **dev-harness** (a softwarehouse: metodologia
de engenharia), **harness-hardware / harness-mecanico** (sementes das próximas verticais).

---

## 6. O norte (para onde vamos)

Resumo; o detalhe Now/Next/Later está no `ROADMAP.md`.

- **Curto:** esquema de eventos→superfície (instrumenta tudo, destrava a interface); validadores
  determinísticos como primitiva da spec (o salto anti-alucinação); gate externo de CI (tira o gate da mão
  do agente, estreia no Logisti).
- **Médio:** curador **age** (fatia 3 — testa modelo novo em sombra + certifica antes de mudar o catálogo);
  spec-kit rodando no Logisti (validação real); semente da camada de conhecimento (grafo md com
  proveniência/confiança/licença, ontologia emergente, "gap map").
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
3. **`docs/design/interface-briefing.md`** — a visão completa da interface viva (Flint), com
   status de maturidade de cada capacidade. O "como o dono quer ver a fábrica".
4. **`motor/docs/EVOLUCAO.md`** — o norte do **motor**: os vetores aditivos (validadores
   determinísticos, eventos tipados, curador-catraca, spec v0.2, fronteira fractal, fábrica de
   especialistas). Regra de ouro: melhorar, não substituir.
5. **`motor/docs/ARQUITETURA-MCP.md`** — a **fronteira**: como o motor vira MCP, e a linha entre
   o que o motor faz e o que o porteiro/orquestrador faz. Decisões travadas.
6. **`motor/README.md`** — entrada técnica do motor (como rodar, testar, Studio).
7. **`dev-harness/`** — a softwarehouse: metodologia de engenharia (PLAYBOOK, spec-kit, tiers T0/T1/T2,
   security-DoD, `docs/biblioteca-de-validadores.md`, fases). É a primeira "casa".

**Onde vivem os briefings (regra: spec/visão no monorepo; preparo-de-implementação no repo do produto):**
o `docs/design/interface-briefing.md` (a *spec* da interface) fica **aqui** no monorepo,
canônico — o Flint a implementa e a referencia. Os briefings de *terreno de produto* vivem nos repos dos
produtos: **Flint** tem o `BRIEFING-FLINT-superficie-meta-fabrica.md` (cliente MCP, ingestão de eventos,
canvas); **Jarvis** tem o `BRIEFING-JARVIS-orquestrador-meta-fabrica.md` (papel de porteiro/orquestrador,
consumo do motor). O contrato MCP que ambos consomem é canônico e fica no monorepo
(`motor/docs/ARQUITETURA-MCP.md`).

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
