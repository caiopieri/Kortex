# Fase 4 — Roadmap: do build-time ao sistema de escala

> *(continuação da Fase 2/3 — é seu pra renomear)*
>
> **Essência:** a Fase 2 supriu as faculdades que faltam ao **modelo**. Esta fase supre as fases
> do **ciclo de vida** que faltam ao **harness**. Seu framework hoje é excelente da ideia até o
> merge. "Sistema de verdade, nível milhão de usuário" é decidido majoritariamente *depois* do
> merge — sob carga, em produção. Este roadmap fecha esse buraco sem reescrever nada do que existe.

---

## 0. O diagnóstico em uma frase

O harness otimiza o **build-time**. Um sistema real tem cinco fases, e a sua Lei das Fronteiras
de Fase só governa três delas (Research → Plan → Implement). As outras duas — o que vem antes
(arquitetura/escala) e o que vem depois (verificação mecânica + produção) — não estão
instrumentadas. Qualidade em escala não nasce no merge; nasce quando 1M de requisições batem
no sistema às 9h de segunda.

| Fase do ciclo de vida | Faculdade que exige | No harness hoje |
|---|---|---|
| **Plan-time** — arquitetura, NFRs, escala | ADR + requisitos não-funcionais (latência, throughput, capacidade) | Parcial — `spec-template` cobre escopo funcional, não captura escala |
| **Build-time** — o loop de código | FIC: Research → Plan → Implement, PR ≤300, contexto em camadas | **Forte. É o núcleo.** |
| **Verify-time** — o portão | CI que **bloqueia merge**: testes, lint, type-check, SAST, build | **Frágil — o gate é auto-reportado pelo agente** |
| **Run-time** — produção | Observabilidade (logs/métricas/traces), SLOs, error budget, deploy seguro | **Ausente** |
| **Learn-time** — fechar o ciclo | Postmortem → volta pra memória fria (`docs/specs`, ADR) | Mencionado, não instrumentado |

---

## 1. A Lei das Fronteiras de Fase, corrigida

A Fase 2 afirmou: *"o custo de erro é máximo a montante; a alavanca de revisão também."*
Isso é verdade **dentro do build-time**. Estendida ao ciclo completo, a curva de custo é **em U**:

> Erro de **arquitetura** (a montante) → milhares de linhas erradas.
> Erro de **implementação** (meio) → barato, corrigível.
> Erro que **chega a 1M de usuários em produção** (a jusante) → o mais caro de todos: vazamento,
> downtime, perda de dado, multa de LGPD. Custo máximo, e o harness hoje não tem instrumento aqui.

Consequência operacional: o esforço de verificação não pode terminar no diff review. Ele precisa
de **dois portões mecânicos** que o agente não controla — um antes do merge (Verify) e um sinal
contínuo depois do deploy (Run). É isso que os passos abaixo constroem.

---

## 2. Os cinco passos (ordem de implementação)

A ordem segue dependência, não importância: cada passo é fundação do seguinte.

| # | Passo | Resolve | Artefato no harness | Depende de |
|---|---|---|---|---|
| **1** | **Gate externo (CI/CD)** | Gate auto-reportado → gate mecânico que bloqueia merge | `ci/` + `pipeline.yml` + atualização do PLAYBOOK passo 6/7 | — |
| **2** | **Estratégia de testes** | "Teste é obrigatório" → pirâmide que pega bug de escala | `docs/testing-strategy.md` + checklist no DoD | 1 |
| **3** | **NFRs na spec** | Escopo funcional → escala como requisito a montante | seção `[ESCALA]` no `spec-template.md` | — (paralelo a 1) |
| **4** | **Loop de produção** | Harness cego pós-merge → observabilidade + SLOs | `docs/observability-DoD.md` + 4ª fase no FIC | 1, 3 |
| **5** | **Learn-time** | Incidente perdido → postmortem vira memória fria | `docs/postmortem-template.md` + regra de atualização de ADR | 4 |

**Por que começar pelo 1.** Sua própria teoria (P2) diz que o modelo é enviesado a *declarar
sucesso* e a produzir código que *"passa nos testes básicos"*. Logo — pela sua lógica — você
**não pode confiar no agente pra rodar o próprio gate**, e hoje o passo 6 do PLAYBOOK faz
exatamente isso ("codar + rodar o gate"). É o aluno corrigindo a própria prova. O gate precisa
sair da mão do agente e virar máquina neutra. É também o que as métricas DORA (o padrão de fato
pra medir se um workflow de engenharia presta) medem primeiro. Tudo mais (testes, segurança,
escala) pendura nesse portão — sem ele confiável, melhorar o resto é construir no ar.

---

## 3. Passo 1 em concreto — o gate de CI/CD (pronto pra "go")

### O princípio
O `security-DoD.md` e o DoD de testes deixam de ser **checklist que o agente diz ter seguido** e
viram **pipeline que roda em máquina neutra e bloqueia o merge se algo falhar**. O agente propõe;
a máquina decide. Branch protection na `main`: sem CI verde, sem merge — inclusive pra você.

### A estrutura de arquivos (proposta)
```
dev-harness/
  ci/
    README.md                 ← o que cada job faz e por que é gate, não sugestão
    github-actions/
      pipeline.yml            ← template de pipeline (lint · type · test · SAST · build)
    pre-commit-config.yaml    ← gate local barato (roda antes de chegar no CI)
  project-template/
    .github/workflows/        ← o que se copia pra cada repo novo
```

### Os jobs do pipeline (o portão mínimo)
| Job | Ferramenta (por stack — preenchido no AGENTS.md) | Bloqueia merge se |
|---|---|---|
| **lint** | eslint / ruff / etc. | erro de lint |
| **type-check** | tsc --noEmit / mypy | erro de tipo |
| **test** | vitest/jest · pytest — com cobertura como *sinal* | teste falha |
| **sast** | semgrep / CodeQL | vuln acima do limite |
| **secrets** | gitleaks | segredo commitado |
| **build** | build de produção | build quebra |

### O que muda no PLAYBOOK
- Passo 6 (`/fic-implement`): o agente roda o gate **localmente** (pre-commit) como feedback rápido — mas isso é cortesia, não autoridade.
- Passo 7 (Validar): o **gate real é o CI**, não o relato do agente. Sua revisão do diff acontece *sobre um PR já verde*. Você nunca mais revisa código que não passou na máquina.
- Decisão travada nova: **branch protection ligado; CI verde é pré-condição não-negociável de merge.**

### Custo e honestidade
Setup inicial: ~meio dia por stack pra calibrar as ferramentas. Depois, custo marginal ~zero —
roda sozinho. O risco real não é técnico, é de disciplina: pipeline que vira lento ou flaky o
time aprende a ignorar (ou a dar `--no-verify`). Mantê-lo rápido (<5 min) e determinístico é o
que o mantém vivo.

---

## 4. Esboço dos passos 2–5 (pra você ver o destino)

**Passo 2 — Estratégia de testes.** Hoje o DoD diz "teste é obrigatório". Bug de escala (N+1,
race condition, vazamento de memória, contenção de lock) não cai em teste unitário. A pirâmide
explícita: muito unitário rápido · integração nos limites (banco, fila, API externa) · contrato
entre serviços · pouquíssimo e2e · **teste de carga** nos caminhos quentes. Cobertura é sinal,
nunca meta — perseguir 100% gera teste inútil.

**Passo 3 — NFRs na spec.** Nova seção `[ESCALA]` no `spec-template`: latência-alvo (p95/p99),
throughput esperado, volume de dados em 1 ano, limites de recurso, o que degrada graciosamente
sob pico. Pela Lei das Fronteiras, "1M de usuários" é mais barato de acertar aqui, na spec, do
que descobrir em produção. É a faculdade de **escopo** estendida ao não-funcional.

**Passo 4 — Loop de produção.** O FIC ganha uma 4ª fase: **Observe**. `observability-DoD.md`
como gate: todo serviço emite logs estruturados, métricas e traces (OpenTelemetry é o padrão);
SLOs definidos (ex.: 99,9% de disponibilidade, p99 < 300ms); error budget que, esgotado, **trava
feature nova e força estabilização**. É o que transforma "achei que estava funcionando" em dado.

**Passo 5 — Learn-time.** `postmortem-template.md` blameless: todo incidente vira documento
(linha do tempo, causa-raiz, ação corretiva) que **volta pra memória fria** — `docs/specs` e ADR.
Fecha o ciclo: o sistema aprende com a própria falha em vez de repeti-la. É a sua "atualização de
memória fria" do PLAYBOOK, agora instrumentada.

---

## 5. Como isto se conecta ao que já existe

- **Não reescreve nada.** Estende o FIC (Research → Plan → Implement → **Observe**) e adiciona
  docs ao lado dos que existem (`security-DoD.md`, `spec-template.md`).
- **Mesma filosofia.** Continua sendo "engenheirar o ambiente, não o modelo" — só que agora o
  ambiente inclui o pipeline e a produção, não só a janela de contexto.
- **Mesma medição.** Os indicadores da Seção 7 da Fase 2 ganham os quatro do DORA por cima:
  frequência de deploy, lead time, change failure rate, MTTR. São o termômetro de que o workflow
  melhorou de verdade — não opinião.
- **Validação primeiro.** Como o HANDOFF já diz: nada disto vira método antes do primeiro uso
  real. O passo 1 deve estrear no Logisti (a migração Supabase já exercita SAST + RLS no gate).

---

## Onde isto pode dar errado

- **Overhead real.** Para script descartável ou protótipo, montar CI + observabilidade custa mais
  do que economiza. Tudo isto vale onde o erro é caro: produção, escala, time. Projeto de fim de
  semana não precisa de SLO.
- **Gate teatral.** Um pipeline lento, flaky ou cheio de check inútil o time aprende a burlar.
  CI que não é rápido e determinístico é pior que não ter — dá falsa segurança e vira atrito.
- **Observabilidade vira ruído.** Métrica e log demais é tão cego quanto de menos (é o seu próprio
  princípio: Qualidade = Correção × Completude ÷ **Ruído**). SLO mal escolhido mede o que não importa.
- **Não substitui julgamento.** Os dois portões mecânicos pegam o conhecido. Falha de escala nova
  e fluxo que toca dinheiro/dado pessoal ainda exigem um humano olhando — o gate reduz, não elimina,
  a sua responsabilidade.
- **Falta validação sua.** Isto é síntese das práticas consolidadas (trunk-based, DORA/Accelerate,
  pirâmide de testes, SRE/SLO). Vira *seu* método quando sobreviver ao primeiro Logisti.
