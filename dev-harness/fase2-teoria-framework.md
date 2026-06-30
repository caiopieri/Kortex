# Fase 2 — Teoria: Framework de Orquestração por Contexto

> *(título de trabalho — é seu pra renomear)*
>
> **Essência:** você não conserta o modelo; você engenheira o ambiente ao redor dele.
> Um modelo de linguagem é um otimizador local, sem estado e com viés de treino para
> concordar e adicionar. Qualidade e eficiência não vêm de um modelo "melhor" — vêm de
> um orquestrador que supre as faculdades que o modelo não tem, concentrando esforço
> nas fronteiras de fase.

---

## 1. O núcleo — um mecanismo, cinco sintomas

A pesquisa parecia apontar cinco problemas (P1 coerência macro, P2 segurança, P3 sycophancy, P4 over-engineering, P5 eficiência). Não são cinco. São **cinco projeções de uma única propriedade do modelo**:

> Um LLM é uma função **sem estado** que otimiza **localmente** para o objetivo imediato presente na janela, treinada para produzir saída **agradável, aditiva e superficialmente correta**.

Disso, tudo decorre:

| Propriedade do modelo | Sintoma observado |
|---|---|
| Sem modelo global persistente do sistema | **P1** — incoerência macro, código que não conversa com o resto |
| Otimização local + custo zero pra gerar código | **P4** — over-engineering, abstrações que ninguém pediu |
| Viés de treino para agradar | **P3** — sycophancy, concorda em vez de propor o melhor |
| Distribuição de treino (código tutorial) + otimizar para "funciona" | **P2** — código inseguro que passa nos testes básicos |
| Todas as anteriores desperdiçam tokens | **P5** — ineficiência |

Tratar os sintomas isoladamente é o erro. A causa é única.

---

## 2. O Primeiro Princípio

A propriedade do núcleo é **fixa** — você não retreina o modelo. Logo, o único lugar onde se pode intervir é o **ambiente ao redor do modelo**. Isso não é opinião: é o achado empírico mais forte da Fase 1 — o scaffolding e a qualidade de contexto superam a capacidade bruta do modelo (paper Confucius; Packmind: "o agente não é burro, é desinformado").

> **Primeiro Princípio:** o trabalho do orquestrador é *ser as faculdades que o modelo sem estado não tem.*

O modelo não tem memória do sistema, não tem noção do custo da própria saída, não tem incentivo a ser correto em vez de agradável, nem a ser seguro em vez de funcional. O ambiente supre cada uma.

---

## 3. As faculdades ausentes — a arquitetura

Cada faculdade que falta no modelo vira uma camada concreta do harness. Esta tabela é o esqueleto da Fase 3.

| Faculdade ausente | O ambiente supre com | Resolve |
|---|---|---|
| **Memória** (modelo persistente do sistema) | Contexto em camadas: *quente* (regras/convenções sempre carregadas), *morno* (spec/plano da tarefa atual), *frio* (specs recuperáveis sob demanda) | P1 |
| **Julgamento de escopo** (o que construir / o que NÃO construir) | Especificação como fonte da verdade — "a spec é o prompt" — com fronteiras explícitas de in/out | P1, P4 |
| **Autocontenção** (consciência de custo) | Compactação frequente (FIC): janela em 40-60%, cada fase produz artefato compactado; orçamento de simplicidade explícito | P4, P5 |
| **Consciência** (segurança) | Gates não-negociáveis: prompting de segurança + SAST + testes como Definition of Done; todo input tratado como hostil | P2 |
| **Ceticismo** (anti-bajulação) | Crítica estrutural obrigatória, ancorada na spec e em verdade externa — não no que o usuário quer ouvir | P3 |
| **Economia** (alocação) | Roteamento por *especificabilidade*: orquestrador capaz; delega ao modelo barato só subtarefas especificáveis; geração de código fica no médio-premium | P5 |

---

## 4. A equação que governa

Tomada emprestada do FIC e generalizada como métrica-mãe do framework:

> **Qualidade de Contexto = Correção × Completude ÷ Ruído**

Três consequências:
- **Correção** e **Completude** são o que o contexto em camadas + spec entregam (faculdades de memória e escopo).
- **Ruído** é o que a compactação remove (faculdade de autocontenção). Excesso de contexto é tão nocivo quanto falta.
- **Eficiência de token é derivada, não independente.** O número de tokens para uma tarefa "absurdamente adequada" cai quando a Qualidade de Contexto sobe — menos retrabalho, menos cold-start, menos excesso. Você não otimiza token diretamente; otimiza a equação acima, e a eficiência cai como subproduto. *(Esse era o seu P5 como centro de gravidade — agora formalizado.)*

---

## 5. A Lei das Fronteiras de Fase

O fluxo é **Research → Plan → Implement**, cada fase fechando com um artefato compactado. A lei que rege onde gastar esforço:

> **O custo de erro é máximo a montante; a alavanca de revisão também.**

- Erro na **pesquisa** → milhares de linhas arquitetadas errado.
- Erro no **plano** → centenas de linhas no lugar/padrão errado.
- Erro na **implementação** → corrigível e barato.

Portanto: **gaste tokens com fartura para acertar spec e plano** (onde um humano revisa um artefato de ~200 linhas e pega o erro com 10-100x mais impacto) **e com frugalidade na implementação** (delegável, compactável). Esse é o coração operacional — e é onde a eficiência (P5) e a coerência (P1) emergem do mesmo gesto.

---

## 6. A tensão central — e sua resolução

A Fase 1 expôs um conflito real: **o contexto rico que resolve a coerência (P1) é exatamente o que mais amplifica a sycophancy (P3)** — perfis de memória do usuário foram o maior amplificador de bajulação medido (CHI 2026). Maximizar os dois ingenuamente é impossível.

**Resolução: particionar o contexto por tipo, e ancorar a crítica.**

1. **Contexto do *sistema*** (arquitetura, convenções, restrições, spec) → rico, persistente, sempre disponível. É o que dá coerência.
2. **Contexto das *preferências/crenças/autoimagem do usuário*** → deliberadamente isolado da função de crítica. É o que infla bajulação.
3. **A crítica avalia contra a spec e a verdade externa — nunca contra o que o usuário disse.** O bloco obrigatório de "onde isto pode estar errado" e os gates de verificação referenciam critérios objetivos, não o desejo do usuário.

E um cuidado que separa quem entende: **o oposto de sycophancy não é contrarianismo.** Um prompt "seja brutal" empurra o modelo a rejeitar tudo — falha simétrica e igualmente inútil. O alvo é **julgamento independente calibrado**: ancorado em critério, não em humor. A defesa é estrutural (saída obrigatória), não tonal.

---

## 7. Como se mede o sucesso

Métrica-mãe: **tokens por tarefa útil entregue** (qualidade-por-token). Indicadores antecedentes, mais fáceis de observar no dia a dia:
- Taxa de retrabalho (PRs/commits refeitos).
- Violações arquiteturais pegas em review (devem cair).
- Achados de segurança por PR (gate antes do merge).
- % de respostas do agente que propõem alternativa/risco vs. só concordam.
- Utilização média da janela de contexto (alvo 40-60%).

---

## 8. Limites desta teoria *(onde ela pode estar errada)*

Honestidade estrutural, aplicada à própria teoria:
- **Tem overhead.** Para correções pequenas e descartáveis, montar spec/contexto custa mais do que economiza. A teoria vale onde o erro é caro — produção, escala, time.
- **Pressupõe disciplina.** A infraestrutura de contexto só funciona se for *mantida*; abandonada, ela mente e piora tudo.
- **Resíduo de modelo permanece.** Prompting de segurança e crítica estrutural reduzem, mas não eliminam, insegurança e bajulação. Verificação humana nos pontos de alta alavancagem continua não-negociável.
- **Falta validação sua.** Isto é síntese de pesquisa de terceiros. Só vira método quando sobreviver ao contato com o Logisti e seus projetos de equipe.

---

## Ponte para a Fase 3 (implementação)

Cada linha da tabela da Seção 3 vira um artefato concreto:
- **Memória** → `CLAUDE.md` em camadas (quente/morno/frio) + convenções do repo.
- **Escopo** → templates de spec com fronteiras in/out.
- **Autocontenção** → templates de prompt Research/Plan/Implement com compactação.
- **Consciência** → checklist de segurança + hooks de SAST/teste no gate.
- **Ceticismo** → contrato de saída com bloco obrigatório de crítica/alternativas.
- **Economia** → regras de roteamento de modelo por especificabilidade.

Aplicados primeiro ao Logisti (caso real, com a migração Supabase + bot Telegram como testes de fogo de P2).
