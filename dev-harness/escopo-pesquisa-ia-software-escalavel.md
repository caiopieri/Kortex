# Escopo de Pesquisa — IA para Software Completo, Coerente e Escalável

> Objetivo macro: descobrir como fazer um agente de IA (Claude Code e similares) produzir
> software **production-grade** — coerente com a arquitetura, seguro, sem excesso e fiel ao
> escopo — em contextos reais (empresa, milhões de usuários, centenas de devs).
>
> Critério-alvo não é só qualidade, é **qualidade por token**: o menor custo possível para uma
> tarefa "absurdamente adequada" ao escopo e ao pedido. Eficiência é objetivo de primeira classe.

---

## 1. Contexto e problema

O uso de agentes de IA para desenvolvimento funciona bem na execução pontual, mas degrada
quando o critério é qualidade de sistema, não de tarefa. Os sintomas observados:

- **Incoerência macro** — cada tarefa é resolvida isolada; o código novo não conversa com o resto.
- **Segurança e qualidade frágeis** — código que "funciona" mas tem falhas e ignora boas práticas.
- **Sycophancy** — o agente concorda com o que foi dito em vez de propor a melhor opção.
- **Fuga de escopo / over-engineering** — cumpre o pedido literal, mas extrapola ou ignora os limites.

A régua aqui é de **código real de empresa**, não de projeto pessoal: o que é tolerável num script
solo é inaceitável num monorepo com centenas de devs.

---

## 2. Diagnóstico — por que isso acontece (hipóteses de causa-raiz)

A pesquisa ataca causas, não sintomas. Hipóteses a validar:

1. **Modelo local, não global** — o agente otimiza a tarefa imediata com o contexto da janela; não mantém um modelo persistente do sistema inteiro. → gera incoerência macro.
2. **Janela de contexto limitada** — ele não "vê" o repositório todo; decide sobre um recorte. Sem memória arquitetural, quase parte do zero a cada tarefa.
3. **Viés de utilidade/concordância** — treino por feedback humano premia respostas agradáveis e que atendem o pedido. → sycophancy.
4. **Custo marginal zero de código** — adicionar código não "dói" pro modelo. Sem orçamento de simplicidade explícito, o default é somar, não remover. → over-engineering.
5. **Distribuição dos dados de treino** — muito código de tutorial, pouco production-hardened. → segurança e edge cases subrepresentados.
6. **Otimização por tarefa, não por sistema** — o agente é "recompensado" por fechar o ticket, não por melhorar a saúde do sistema no tempo.

---

## 3. As três fases

| Fase | Entrega |
|------|---------|
| **1. Pesquisa** | Levantamento das técnicas existentes + evidências + classificação *controlável vs. inerente ao modelo*. |
| **2. Teoria** | Um modelo/framework conceitual que costura as técnicas num método coerente de trabalho com IA. |
| **3. Implementação** | Artefatos concretos (CLAUDE.md, regras, checklists, hooks, workflow passo a passo) aplicados aos seus projetos. |

---

## 4. Fase 1 — Pesquisa: o que vamos investigar

Organizado pela sua priorização. Cada item é uma pergunta a responder com evidência.

### P1 — Visão macro / arquitetura coerente *(prioridade máxima)*
- Como dar ao agente um **modelo persistente do sistema** (ADRs, diagramas C4, docs de arquitetura que ele lê e mantém)?
- **Context engineering**: o que carregar na janela e como (RAG sobre o repo, índices, arquivos de memória como `CLAUDE.md` / `AGENTS.md`)?
- Workflows **design-first / spec-driven** — escrever spec e design antes do código; ferramentas emergentes do tipo "spec kit".
- **Decomposição com papéis** — um agente "arquiteto/lead" que detém a visão e valida o trabalho de subagentes.
- Como empresas grandes (monorepos, muitos devs) integram agentes sem quebrar a coerência.
- Revisão automática que checa **aderência arquitetural**, não só sintaxe.

### P2 — Segurança e boas práticas
- **Definition of Done executável**: testes, lint, type-check e SAST como gates obrigatórios no loop do agente.
- Checklists de segurança injetadas no harness (OWASP, validação de input, secrets, authz).
- Abordagem **test-driven** — o agente escreve testes antes.
- **Passe de revisão de segurança** por um segundo agente/crítico.
- Como medir qualidade objetivamente (cobertura, complexidade ciclomática, vulnerabilidades) e fechar o loop.

### P3 — Sycophancy
- Técnicas de prompt/sistema que **forçam trade-offs e alternativas** em vez de concordância.
- Passes de **crítica / advogado do diabo / red-team** do próprio plano.
- Pedir **opções com prós e contras** em vez de validação binária ("isso tá certo?").
- Quanto disso é controlável via processo vs. limite do modelo.

### P4 — Escopo / over-engineering
- **Fronteiras de escopo explícitas** por tarefa (o que está dentro / fora).
- Regras de **simplicidade** (YAGNI, orçamento de complexidade).
- Revisão dedicada a "o que foi adicionado além do pedido?".
- Specs que delimitam também o que **NÃO** fazer.

### Transversal (atravessa tudo)
- Para **cada técnica**: é controlável por você (prompt/harness/processo) ou é limite inerente do modelo? Essa separação é o que torna a pesquisa acionável.
- Fontes a priorizar: documentação oficial (Anthropic / Claude Code), papers, relatos de engenharia de empresas, ferramentas emergentes.

### P5 — Eficiência de token / alocação de modelo *(centro de gravidade)*
- A **qualidade do scoping do pedido pelo orquestrador** é a alavanca única que governa qualidade *e* custo. Investigar como medir e melhorar isso.
- Boa parte do desperdício de token é **emergente** de P1–P4: over-engineering (P4), retrabalho por incoerência (P1) e cold-start de contexto (P1). Resolver essas reduz custo como subproduto.
- Camada genuinamente separada: **qual modelo faz qual subtarefa**. Delegar a modelo barato compensa em token *somente quando a subtarefa é especificável o bastante pra dispensar julgamento inline*; tarefas exploratórias delegadas geram retrabalho = mais token.
- Pesquisar: como times decidem essa alocação (cheap vs. capable), e métricas de "tokens por saída útil".

---

## 5. Critérios de sucesso

A pesquisa estará "pronta" quando tivermos:
- Um conjunto de práticas **validadas e priorizadas** (não só listadas).
- Aplicáveis tanto **solo** quanto em **time**.
- Que atacam **causa-raiz**, não sintoma.
- **Mensuráveis** — dá pra saber se melhorou (ex.: menos retrabalho, menos código morto, menos falhas em review, **menos tokens por tarefa útil entregue**).

---

## 6. Fora de escopo (por enquanto)

- Treinar ou fine-tunar modelos próprios.
- Construir ferramentas do zero — só se a pesquisa apontar necessidade real.
- Comparação exaustiva de todos os modelos do mercado.

---

## 7. Próximo passo

Iniciar a **Fase 1 (Pesquisa)** atacando P1 (visão macro / arquitetura) primeiro, já com a
lente "controlável vs. inerente" aplicada a cada técnica encontrada.
