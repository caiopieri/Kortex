# Decisão — Ciclo de vida do workflow (autoria, catálogo, versão, composição)

> **Canônico.** Fonte única de como um workflow nasce, é personalizado, versionado, executado
> (inclusive parcialmente) e melhorado ao longo do tempo. Companheiro de
> `motor/docs/EVOLUCAO.md` (vetores do motor) e `../motor/motor/spec.py` (a WorkflowSpec real).
> Se algum doc conflitar com este no tema "workflow", **este vence**. Decisão registrada em
> 2026-07-03.

## Por que este doc existe
Este documento registra o contrato de criação e evolução de workflows para que implementação,
interface e documentação permaneçam compatíveis.

## 1. O que é um workflow (o objeto)
Um **workflow é uma WorkflowSpec** — dado tipado, inspecionável, versionado (`motor/motor/spec.py`).
A **dinâmica vive na spec, não no código do grafo.** Dois conceitos que não se confundem:

- **Template** = um workflow nomeado e reutilizável (ex.: "criação de personagens", "software").
  É um **menu de papéis** com dependências, gates e rubricas padrão.
- **Missão** = uma execução concreta. A missão **instancia** um template e **seleciona** o que
  precisa. A spec da missão é, muitas vezes, um **subconjunto** do template.

## 2. Catálogo de workflows (o registro)
Existe um **catálogo de templates versionados**, cada um com metadados **"quando usar"**. É o
análogo da escada de modelos, mas de workflows. O usuário cadastra o seu, descreve pra que serve,
e o **Orquestrador seleciona o template certo** pra cada missão (roteamento no nível de template).
Software já é isto: o **consenso de engenharia codificado** no `dev-harness` (a softwarehouse) —
não é inventado por missão, é o template que as missões instanciam. Novos domínios (design) ganham
o seu próprio template, semeado por pesquisa (ver §3).

## 3. Autoria como uma run do motor (dogfooding)
Criar um workflow novo **é uma missão do motor**. O fluxo previsto é:
1. Usuário: "sinto falta de um workflow de design, vamos fazer?"
2. **Orquestrador** conduz: propõe uma **pesquisa profunda de mercado** (padrão de indústria),
   **arquiteta** a pesquisa pra ela valer de todos os lados, roda → **sintetiza** → **rascunha a
   WorkflowSpec**. Isso é o motor rodando (pesquisa → síntese → artefato = uma spec).
3. Usuário revisa, pede ajustes. Ver o guardrail no §6.
4. Fecha, cataloga a v1, começam as runs.

Consequência: **a fábrica constrói os próprios workflows com a própria máquina.** É a mesma
recursão de "treinar um especialista é uma run gated do motor" (EVOLUCAO V6), aplicada à autoria.

## 4. Personalização e o limite de topologia
O usuário (e quem mantém os workflows) **edita a spec livremente**: adicionar/remover agentes,
ligar/desligar dependências, inserir validador determinístico, inserir gate. **Workflow novo =
todo dia, livre.** O único limite: a **topologia** fica em **dois padrões certificados**
(`fan_out_sintese` paralelo; `grafo_dependencias` = qualquer DAG). Qualquer pipeline real é um
DAG, então a liberdade é ampla; o que **não** se faz é inventar uma *estrutura de controle* nova
(um loop/branch que o motor não sabe verificar) — isso é **padrão novo**, raro, entra como versão
de spec certificada em código. Traduzindo: **workflow novo ≠ padrão novo.** O editor visual
oferece só a gramática válida e **valida ao vivo** (rejeita ciclo, dependência quebrada, validador
que se auto-valida, nó sem rubrica); spec inválida **não dispara**.

## 5. Versionamento com evidência (a certificação)
Todo workflow é **versionado**. Regras:
- A alteração do usuário = **nova versão**, por conta dele, **reversível se der ruim**.
- Cada versão **carrega a evidência de como performou** (do livro-razão do curador): aprovação de
  1ª tentativa, custo, latência, convergência. "v3 bateu v2 em custo e qualidade" fica **registrado**.
- **Versão + evidência = certificação.** É a disciplina "só dado gate-verificado promove" aplicada
  à evolução do workflow. Uma versão sem evidência é candidata, não titular.

## 6. O guardrail da medição (melhor/pior é dado, não opinião)
Quando o usuário propõe uma mudança, o agente **não afirma** "isso piora o fluxo" por opinião —
seria o "plausível-errado" que o método manda desconfiar. A forma correta:
> "Acho que isso pode engasgar por X; deixa eu **rodar em sombra** pra confirmar antes de
> comprometer." → roda → "confirmado, sua versão reprovou mais e custou mais, olha os números"
> **ou** "me enganei, a sua é melhor, vamos manter."

**A palavra final é do dado** (run em sombra ou telemetria histórica do curador), não do agente.
É a **fatia 3 do curador** (sombra + certificação). O agente pode *suspeitar e explicar*; só a
medição *decide*.

## 7. Execução parcial e modo MVP (rodar só um pedaço)
A missão **não é obrigada a rodar o template inteiro**:
- **Seleção de escopo:** "só a voz" de um template de personagens = uma missão com o nó da voz
  (+ dependências + validador), sem corpo/aparência. Papéis são **primitivas reutilizáveis**; a
  missão monta os nós que quer (inclusive de templates diferentes).
- **Perfil barato / MVP:** um perfil de disparo que **solta gates/validadores/escalada** pra um
  rascunho exploratório (as opções já existem em §8.3 do brief: `--auto`, escalada on/off,
  reconciliação on/off, gate de cobertura on/off).
- **Trava honesta (anti-collapse):** run com garantias soltas sai **marcado como
  "rascunho / não-certificado"** e **fica fora do corpus do curador/flywheel**. Pode, é útil, mas
  **não pode se passar por certificado** — dado não-verificado não vira sinal de treino nem
  evidência de versão.

## 8. Composição entre casas (voz → software house → volta)
Compor pedaços de workflows/casas diferentes segue a arquitetura em camadas:
- O artefato de um run (a "voz") sai como **artefato tipado com proveniência** e entra como
  **entrada** de outro run (na software house). O `Subagente` já tem `entradas` e
  `produz_artefatos`.
- A segunda missão é a spec dela, **enxuta** — não passa pelo processo todo.
- **Quem encadeia** os runs entre casas é o **Orquestrador** (camada acima do motor). O motor roda
  **um** artefato; a casa coordena muitas runs; o orquestrador coordena casas (decisão pétrea #5).
- **Trava:** a fronteira entre casas exige **contrato tipado** (o artefato carrega tipo +
  proveniência). Sem isso, a composição vira "prosa solta" e reproduz inconsistência um nível
  acima — é o mesmo motivo do handoff tipado dentro do motor (EVOLUCAO V5).

## 9. Papéis (quem faz o quê aqui)
- **Orquestrador** — parceiro de **autoria e execução**: conversa pra criar o workflow, dispara a
  pesquisa, monta, seleciona template, encadeia runs entre casas. Interativo.
- **Curador** — cérebro de **medição e melhoria contínua**: observa as runs ao longo do tempo e
  **propõe** mudanças **com evidência** (→ Caixa do Fundador). É quem "vai trazendo melhorias e
  coisas novas do mercado" depois que as runs começam. Não co-autora no chat; mede.
- **Fundador (humano)** — aprova versões e propostas; suas alterações são responsabilidade dele,
  versionadas e reversíveis.

## 10. O que NÃO fazer (guardas)
- **Não é n8n de fios livres.** Topologia = dois padrões certificados; padrão novo = versão de
  spec, raro.
- **Run barato não mascara de certificado.** Sempre marcado; fora do corpus do flywheel.
- **Agente não decreta "melhor/pior"** sem sombra/telemetria. Opinião suspeita; dado decide.
- **Composição sem contrato tipado na fronteira** é proibida (vira prosa solta).
- **Orçamento/permissão/org não entram no motor** por causa disto (decisão #5) — a coordenação
  entre casas é da camada de casa/orquestrador.

## Referências
- WorkflowSpec real: `../motor/motor/spec.py` (padrões, `Subagente`, `GateFundador`, validação).
- Vetores do motor: `../motor/docs/EVOLUCAO.md` (V1 validadores, V3 curador, V4 fractal, V5 spec).
- Visão/camadas/princípios: `ARCHITECTURE.md`. Mapa operacional: `ROADMAP.md`.
- Contrato da interface: `../motor/specs/002-painel-operacional/spec.md`.
