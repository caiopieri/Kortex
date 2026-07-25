# Adoção do spec-kit — migrar o harness pra base profissional

> Decisão (Fase 4): adotar o **github/spec-kit** como motor do fluxo, e injetar os ativos únicos
> do nosso harness (teoria, security-DoD, tiers, anti-bajulação) como **constitution** — a lei que
> o spec-kit obedece em toda fase. Não jogamos nada fora: movemos para onde a máquina pronta lê.
>
> Por que adotar e não manter o bespoke: você reinventou o spec-kit sozinho. A arquitetura é a mesma
> (`specify → clarify → plan → tasks → analyze → implement`). Manter motor próprio é manutenção sem
> retorno; o valor que é *seu* — a teoria e a segurança — sobrevive na constitution e nos templates.

---

## 1. O que mapeia onde

| Ativo do harness | Vai para | Observação |
|---|---|---|
| Teoria (Fase 2): faculdades ausentes, qualidade de contexto | **Constitution** — Core Principles | Vira a lei que governa specs/planos |
| `security-DoD.md` (multi-stack, CVEs reais) | **Constitution** — Seção "Security Requirements" + `/speckit.checklist` | Gate, não sugestão |
| Tiers T0/T1/T2 | **Constitution** — Seção "Quality Gates / Workflow" | Define quanto processo roda |
| Anti-bajulação + "onde pode dar errado" | **Constitution** — Governance | Saída obrigatória, ancorada em critério |
| Fase 4 (CI gate, observabilidade, NFR) | **Constitution** — Security/Performance + extension futura | NFR também na spec (já tem P1/P2/P3) |
| `spec-template.md` próprio | **aposenta** | spec-kit já traz spec com fatias P1/P2/P3 testáveis |
| `fic-research / fic-plan / fic-implement` | **aposentam** | substituídos por `/speckit.plan` etc. |
| `PLAYBOOK.md` (processo do humano) | **mantém** — vira manual de como rodar o spec-kit | Atualizar os comandos |
| `discovery-template.md` + `ROADMAP-template.md` | **mantêm** — camada acima do spec-kit | Tool-agnósticos |
| `AGENTS.md` / `~/.claude/CLAUDE.md` | **mantêm**, enxutos | Specifics do repo; constitution cobre o universal |

O que o spec-kit te dá de graça que você ainda não tinha: `/clarify` (= seu Discovery dentro do fluxo), `/analyze` (consistência entre artefatos = ataque mecânico ao P1), `/checklist` ("testes unitários pro inglês" da spec), e `/tasks` (decomposição com dependências e marcadores `[P]` de paralelismo).

---

## 2. Instalação (no Logisti, como teste de fogo)

Pré-requisitos: Python 3.11+, uv, git, Claude Code.

```bash
# instala a CLI
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

# inicializa no repo do Logisti (Claude Code como agente)
cd <repo-do-logisti>
specify init . --integration claude
```

Isso cria `.specify/` (memory, scripts, templates) e os comandos `/speckit.*` no Claude Code.

---

## 3. A constitution — cole isto em `/speckit.constitution`

> Esta é a tradução da Fase 2 + security-DoD + tiers para a linguagem da constitution.
> Rode `/speckit.constitution` com este conteúdo (ajuste nomes de stack ao Logisti).

```text
Crie a constitution com estes princípios e seções, governando spec, plan, tasks e implement:

PRINCÍPIO I — Ambiente sobre modelo (NÃO-NEGOCIÁVEL).
O agente é um otimizador local sem estado, treinado a agradar e adicionar. Qualidade vem do
contexto, não de "esforço" do modelo. Specs e planos são a fonte da verdade; quando o requisito
muda, edita-se a spec, nunca se improvisa no código.

PRINCÍPIO II — Escopo é lei. Toda spec declara escopo dentro E fora explícitos. O agente não
infla a tarefa. Over-engineering é violação: a abstração que ninguém pediu não entra.

PRINCÍPIO III — Tier define o rigor.
T0 (spike, descartável): sem gate. T1 (MVP): segurança inegociável + teste no caminho crítico.
T2 (produção/escala): gate completo. O tier é declarado antes do plano e promovê-lo é decisão
consciente, nunca por inércia.

PRINCÍPIO IV — Teste pragmático (NÃO-NEGOCIÁVEL em T1+). Teste no caminho crítico é obrigatório;
test-first para lógica de negócio, test-after para UI/cola. O agente NUNCA apaga teste sem
autorização. Cobertura é sinal, não meta.

PRINCÍPIO V — Ceticismo ancorado. Toda proposta termina com "Onde isto pode dar errado",
avaliado contra a spec e a verdade externa — nunca contra o que o usuário quer ouvir. O oposto
de bajulação não é contrarianismo: é julgamento calibrado por critério.

PRINCÍPIO VI — Spec à prova de executor barato. Toda spec/tarefa declara o TIER DO EXECUTOR
(premium | médio | barato). Se o executor é de tier barato (DeepSeek/Kimi ou equivalente), a
spec OBRIGATORIAMENTE: (a) fixa interfaces e assinaturas — o executor não desenha API; (b) lista
os arquivos a tocar, e tocar fora da lista é violação; (c) tem critérios de aceitação EXECUTÁVEIS
(testes escritos a montante; o DoD é a suíte passar, nunca juízo do executor); (d) proíbe o
executor de editar testes — teste que parece errado = parar e reportar; (e) converte ambiguidade
em escalação: o executor barato não decide, devolve a pergunta ao planner. Tarefa que não admite
essa forma (design aberto, trade-off, segurança) NÃO desce de tier — sobe pro premium.

SEÇÃO — Security Requirements (gate por stack; aplicar as que o projeto usa):
Universal: validar todo input; autorização (não só autenticação) em cada endpoint; zero segredo
no código; erro não vaza interno; queries parametrizadas; SAST antes do merge.
Supabase/Postgres: RLS ligada em toda tabela com dado de usuário; policies testadas (A não lê B);
service_role só no servidor. Bot/LLM: conteúdo de terceiro é dado, nunca instrução; saída do
modelo validada e tipada antes de tocar o banco; ação sensível pede confirmação fora do canal.

SEÇÃO — Performance & Scale (T2): toda spec T2 declara latência-alvo (p95/p99), throughput,
volume de dados em 1 ano, e o que degrada graciosamente sob pico.

GOVERNANCE: a constitution supera qualquer preferência. Todo plano e revisão verificam
conformidade. Complexidade precisa ser justificada. O agente roda em sandbox/dev container quando
executa comandos. O orquestrador (humano) revisa o plano e o diff; validação não é delegável.
```

Depois de criada, `/speckit.plan` e `/speckit.implement` passam a referenciar a constitution automaticamente.

---

## 4. O fluxo novo, ponta a ponta

```
ideia
  │
[Discovery]  docs/discovery-template.md → dor, hipótese arriscada, menor teste, TIER, fora-de-escopo
  │
[Roadmap]    ROADMAP.md → coloca a fatia em "Now" (Now/Next/Later)
  │
  ▼  ─────────── por fatia, no spec-kit ───────────
/speckit.specify   → spec da fatia (o quê/porquê, sem stack)
/speckit.clarify   → fecha vãos (antes do plano)
/speckit.plan      → plano técnico ◄── VOCÊ REVISA (alavancagem máxima)
/speckit.tasks     → quebra com dependências + [P]
/speckit.analyze   → consistência spec↔plano↔tarefas (pega P1)
/speckit.checklist → qualidade da spec (T1+)
/speckit.implement → código + roda local
  │  ──────────────────────────────────────────────
  ▼
[Gate CI externo]  ← Fase 4 passo 1: máquina bloqueia merge (não o agente)
  │
[VOCÊ] revisa o diff sobre PR verde → merge
  │
[Observe + Learn]  ← Fase 4 passos 4-5 (T2): produção reporta; incidente vira memória
```

---

## 4.1 Roteamento de modelo por fase (a "Economia" da Fase 2, concretizada)

> Princípio: capacidade de raciocínio a montante, frugalidade a jusante. Use por **especificabilidade**,
> não por hábito. Nomes de modelo mudam — verifique a doc oficial antes de cravar; aqui ficam os tiers.

| Fase | Tier de modelo | Por quê |
|---|---|---|
| Discovery, `/specify`, `/clarify`, `/plan`, `/analyze` | **Raciocínio premium** (hoje: Claude Fable 5, jun/2026) | Limitado por raciocínio; é onde o erro custa 10-100x. Pouco token, alta alavancagem. |
| `/tasks`, `/implement` (tarefa bem-especificada, com design) | **Médio** (Sonnet) | Volume de token, tarefa especificável. Modelo premium aqui é dinheiro queimado. |
| `/implement` (tarefa PRINCÍPIO VI: interface fixada + testes prontos) | **Barato/grátis** (DeepSeek v4 / Kimi K2.6 via NVIDIA API, proxy OpenAI-compat) | Custo ~zero; o gate é a suíte de testes, não confiança. Falhou 2-3x nos testes → escala pro Sonnet. Limite: sem tool use confiável via proxy — tarefas texto/código puro. |
| Review de diff que toca camada crítica (kernel, motor, segurança) | **Premium** (Fable/Opus) | Review é barato em tokens vs. escrever; é onde o barato erra silenciosamente. |
| Retrofit / migração grande de legado | **Premium de horizonte longo** (Fable 5, 1M de contexto) | Segurar o sistema inteiro em contexto por sessões longas. |

Dois cuidados da própria Fase 2: (1) o modelo premium **levanta o piso, não dispensa o harness** —
continua sem estado, sem memória do sistema, enviesado a agradar. (2) **Anti-bajulação importa MAIS**
com modelo mais forte: a concordância dele é mais convincente, logo mais perigosa. A crítica ancorada
na spec não relaxa porque o modelo ficou esperto.

## 5. Sequência de adoção (pequeno → consolidar — seu próprio princípio)

1. **Piloto:** `specify init` no Logisti + criar a constitution acima. Rodar UMA fatia T1 ponta-a-ponta (a migração Supabase exercita RLS + SAST).
2. **Consolidar:** se o fluxo encaixar, mover Flint e e-commerces. Aposentar `fic-*` e `spec-template` próprio.
3. **Gate:** ligar o CI externo (Fase 4 passo 1) com branch protection.
4. **Preset (opcional, quando a escala pedir):** empacotar a constitution + checklist de segurança como um *preset* spec-kit reusável entre os repos, em vez de recolar.

---

## Onde isto pode dar errado
- **Lock-in leve.** spec-kit é experimental e da GitHub; pode mudar API. Mitigação: a constitution e os templates são markdown portável — o valor não morre se a CLI sumir.
- **Recolar constitution em cada repo** vira inconsistência. Quando tiver 3+ repos, vira preset (passo 5.4) — antes disso é over-engineering.
- **`/clarify` não substitui o Discovery.** Discovery decide *se e o quê* construir (e o tier); `/clarify` refina uma spec que já existe. São fases diferentes; manter as duas.
- **Pilotar e não consolidar.** O risco real é instalar, achar legal, e voltar ao improviso. Vira método quando sobreviver à primeira fatia real do Logisti — não antes.
