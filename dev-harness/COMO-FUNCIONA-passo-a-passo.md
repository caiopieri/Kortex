# Como funciona na prática — passo a passo (sessão por sessão)

> Dois cenários reais de e-commerce: **(A) do zero** e **(B) pegando no meio** (retrofit).
> Cada "Sessão" é uma janela do Claude Code. `/clear` entre sessões é regra: a continuidade vive
> nos **arquivos** (`.specify/`, `specs/`, `ROADMAP.md`), nunca no histórico do chat. Isso é o FIC —
> contexto limpo a cada fase, sem arrastar ruído.

---

# Cenário A — E-commerce do ZERO

## Sessão 0 — Bootstrap (uma vez no projeto)
No terminal:
```bash
specify init loja --integration claude
cd loja
```
Abre o Claude Code e estabelece a lei do projeto:
```
/speckit.constitution   ← cola o conteúdo de spec-kit-adocao.md (teoria + tiers + security-DoD)
```
→ cria `.specify/memory/constitution.md`. **`/clear`.**

## Sessão 1 — Discovery (você chega e fala tudo que pensa)
Aqui é o "chego no Claude Code e despejo a ideia". Não é comando spec-kit; é o template:
```
Leia docs/discovery-template.md e me ajude a preencher para esta ideia:
"quero uma loja online de [X], cliente acha o produto, põe no carrinho, paga, recebe."
Me desafie — não monte o que eu pedi, ataque a hipótese.
```
A IA te interroga até sair: a dor, a **hipótese mais arriscada** (ex.: "as pessoas compram [X] online?"), o **menor teste**, o **tier**, e o fora-de-escopo. Decisão de tier aqui: loja pra validar mercado começa **T1**; se já é negócio sério com tráfego garantido, nasce **T2**.

No fim, você abre o `ROADMAP.md` e escolhe a **primeira fatia vertical** — não a loja inteira:
> Now: **"catálogo: listar produtos + ver detalhe"** (P1) — a fatia mais fina que entrega valor ponta-a-ponta.

**`/clear`.**

## Sessão 2 — Spec da primeira fatia
```
/speckit.specify  catálogo de produtos: página que lista produtos com foto, nome e preço,
                  e página de detalhe de um produto. Sem carrinho ainda. O quê e porquê — sem stack.
/speckit.clarify  ← responde o que ele perguntar (paginação? busca? esgotado some?)
```
Lê a spec gerada em `specs/001-catalogo/spec.md`, ajusta o que estiver torto. **`/clear`.**

## Sessão 3 — Plano (sua maior alavancagem)
```
/speckit.plan  Next.js + Supabase (Postgres). Catálogo lido via API. Imagens no storage do Supabase.
/speckit.analyze   ← checa consistência spec ↔ plano (pega incoerência cedo)
```
**VOCÊ REVISA o plano** (`specs/001-catalogo/plan.md`) — 200 linhas, é onde o erro é mais barato. **`/clear`.**

## Sessão 4 — Tarefas + implementação
```
/speckit.tasks
/speckit.checklist   ← só T2; "testes unitários pro inglês" da spec
/speckit.implement
```
O agente coda e roda local. O **gate de CI** (máquina, não o agente) roda no PR. Você revisa o **diff sobre PR verde** e dá merge. **`/clear`.**

## Sessões seguintes — próximas fatias
Repete o ciclo Sessão 2→4 para **"carrinho"**, depois **"checkout/pagamento"**. No checkout, a seção *Web/pagamentos* do security-DoD entra automática (preço validado no servidor, nunca confiar no valor do cliente; cartão via processador PCI, nunca cru). Cada fatia = 1 passada pelo funil.

## Quando promover pra T2 (antes do lançamento real)
No `ROADMAP.md`: entrada *"promover loja → T2"*. Ligam: gate CI + branch protection, pirâmide de testes + carga no checkout, NFR nas specs (p95/p99, throughput no pico de venda), observabilidade (SLO: 99,9% checkout < 2s) e postmortem. Endurece **fatia a fatia**, não tudo de uma vez.

---

# Cenário B — E-commerce JÁ NO MEIO (retrofit)

> O caso difícil: já existe código que **nunca passou** por esses cuidados. A regra de ouro:
> **você não para tudo pra reescrever.** Você (1) estabelece a base, (2) audita contra a nova lei,
> e (3) intercala remediação com feature nova. Toca o que toca; e ataca os gaps de risco numa fila própria.

## Sessão 0 — Bootstrap no repo existente
```bash
cd ecommerce-existente
specify init . --here --force --integration claude
```
`--force` mescla o `.specify/` sem apagar seu código. **`/clear`.**

## Sessão 1 — Constitution
```
/speckit.constitution   ← cola a mesma constitution (teoria + tiers + security-DoD)
```
A partir daqui a lei existe — mas o código antigo ainda não a obedece. **`/clear`.**

## Sessão 2 — Baseline: a IA entende o que já existe
> Brownfield exige que o agente conheça o sistema atual antes de tocar nele. Sem isso, ele incoere (P1).
```
Leia o repositório inteiro e produza dois artefatos, sem mudar código:
1. docs/ARCHITECTURE.md — o que existe hoje: stack real, camadas, fluxo de dados, integrações.
2. AGENTS.md preenchido — stack, restrições duras, convenções que o código JÁ segue.
```
Você revisa (a IA pode ter entendido errado). **`/clear`.**

## Sessão 3 — Auditoria contra a constitution (lista, não conserta)
```
Audite o código existente contra a seção Security Requirements da constitution e docs/security-DoD.md.
Liste as violações por severidade (crítica/alta/média). NÃO conserte nada — só produza a lista em
docs/remediation-backlog.md, cada item com arquivo, risco e tier sugerido.
```
Sai um backlog real: ex. *"tabela `pedidos` sem RLS (crítica)"*, *"preço validado no cliente no checkout (crítica)"*, *"sem teste no fluxo de pagamento (alta)"*. Você joga esses itens no `ROADMAP.md`, numa **fila de remediação** separada das features. **`/clear`.**

## Sessão 4+ — Daí em diante: duas filas intercaladas
O `ROADMAP.md` agora tem duas correntes, e você alterna:

**(a) Feature nova** → fluxo idêntico ao Cenário A (specify → clarify → plan → tasks → implement). Uma sessão por fase, `/clear` entre elas.

**(b) Item de remediação** → tratado como uma fatia normal. Ex.:
```
/speckit.specify  ligar RLS na tabela pedidos e escrever policies: usuário só lê/edita o próprio pedido.
/speckit.clarify
                  (/clear)
/speckit.plan     migração SQL + policies + ajuste no que a aplicação confiava sem a policy.
                  ← VOCÊ REVISA (migração é alto risco)   (/clear)
/speckit.tasks → /speckit.implement → gate CI → seu diff review → merge
```

## As duas regras que tornam o retrofit sustentável
1. **Regra do escoteiro:** quando uma feature nova encosta num módulo legado, você aplica o gate **àquele pedaço** ali — não deixa pior do que achou. O sistema melhora por onde você passa.
2. **Fila de risco não espera ser tocada:** gaps **críticos** de segurança (RLS, preço no cliente, segredo exposto) não esperam você "passar por perto" — entram em *Now* na frente de feature nova. O resto remedia incrementalmente.

## Onde o retrofit dá errado
- **Big-bang rewrite.** Tentar reescrever tudo pra "ficar limpo" trava o produto por meses e quase sempre fracassa. Incremental é a única via que entrega.
- **Auditar e não agir.** O `remediation-backlog.md` vira papel morto se os itens críticos não viram *Now*. Auditoria sem fila priorizada é teatro.
- **Feature nova sobre base insegura.** Construir o novo encostando numa tabela sem RLS herda o furo. Por isso o gap crítico vai na frente.
- **Pular a Sessão 2 (baseline).** Mandar a IA mexer no legado sem ela entender a arquitetura atual = incoerência garantida. O entendimento vem antes do toque.

---

## Resumo dos dois fluxos

| | Do zero (A) | No meio (B) |
|---|---|---|
| Bootstrap | `specify init loja` | `specify init . --here --force` |
| Constitution | igual | igual |
| Antes de codar | Discovery → 1ª fatia no Roadmap | + Baseline (ARCHITECTURE/AGENTS) + Auditoria → backlog |
| Loop por fatia | specify→clarify→plan→tasks→implement→gate | **idêntico** (feature nova *e* item de remediação) |
| Ordem | fatia mais fina de valor primeiro | gaps **críticos de segurança** primeiro, depois intercala |
| Promoção a T2 | antes do lançamento, fatia a fatia | conforme o módulo é endurecido |

A constante nos dois: **a unidade de trabalho é sempre a fatia, sempre pelo mesmo funil, sempre com `/clear` entre as fases.** O que muda no retrofit é só o trabalho extra de *entender e auditar o que já existe* antes de o funil começar a girar.
