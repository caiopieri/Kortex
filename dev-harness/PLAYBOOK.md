# PLAYBOOK — Desenvolvimento com IA (manual do administrador)

> Para **você**, que administra. Não é arquivo de agente — é o mapa do processo.
> Duas partes: **(1) o processo que você roda** · **(2) os documentos que você dá aos agentes.**

> **⚠️ ATUALIZAÇÃO (Fase 4 — motor migrado para o spec-kit).**
> O **princípio** abaixo (você é o orquestrador; revisa plano e diff; não delega o julgamento)
> continua válido e é o coração de tudo. O que mudou foi a **mecânica**: o loop por tarefa não
> roda mais com `fic-research/plan/implement` — roda com o **github/spec-kit**.
> - **Antes do funil:** `docs/discovery-template.md` → `ROADMAP.md` (Now/Next/Later).
> - **Loop por fatia:** `/speckit.specify → clarify → plan` (você revisa) `→ tasks → analyze → implement`.
> - **Depois:** gate de CI externo → seu diff review → merge → observe/learn (Fase 4, tiers T0/T1/T2).
> - **Aposentados:** `.claude/skills/fic-*` e o `spec-template.md` próprio (spec-kit já os cobre).
> O passo a passo está em `COMO-FUNCIONA-passo-a-passo.md`.

---

# Parte 1 — O processo (você é o orquestrador)

## Princípio
A IA executa; **você não delega o julgamento.** Seu trabalho é o que a IA não faz bem: definir intenção, aprovar o plano, revisar o diff, manter a arquitetura coerente. Tudo o mais é apoio a isso.

## Quem faz o quê

| Passo | Onde / quem | O quê |
|---|---|---|
| 1. Intenção | Aqui, você + IA | Conversar até o objetivo ficar claro |
| 2. Spec | Aqui, você + IA | Escrever a spec no template → `docs/specs/<task>.md` |
| 3. Quebra | Você | Confirmar que a task é 1 PR ≤ 300 linhas |
| 4. `/speckit.specify` + `clarify` | Agente | Fechar requisito e ambiguidades |
| 5. `/speckit.plan` + `analyze` | Agente → **VOCÊ REVISA** | Plano consistente com a spec. Maior alavancagem: revisar antes do código |
| 6. `/speckit.tasks` + `implement` | Agente | Quebrar, codar e rodar o gate (DoD) |
| 7. Validar | Você + automação | Gate (testes/lint/SAST) + sua revisão do diff |
| → Merge | Você | Aprovar |

## O loop, por tarefa

```
  ideia
   │
   ▼
[1] INTENÇÃO ─── conversa até entender (grooming). Não one-shot.
   │
   ▼
[2] SPEC/PRD ── não-trivial? escreve a spec (template). trivial? pula.
   │
   ▼
[3] QUEBRA ──── epic → tarefas pequenas. 1 tarefa = 1 PR ≤ ~300 linhas.
   │
   ▼   ┌──────── por tarefa ────────┐
[4] /speckit.specify → clarify       │
[5] /speckit.plan → analyze  ◄── VOCÊ REVISA antes do código
[6] /speckit.tasks → implement + gate│
   │   └────────────────────────────┘
   ▼
[7] VALIDA ──── gate automático + seu diff review (+ agente revisor opcional)
   │
   ▼
  merge → atualiza memória fria se houve decisão importante
```

## Respostas diretas às suas perguntas

- **Faço um PRD?** Sim, para tarefa não-trivial — a spec *é* o seu PRD. Proporcional ao risco. Correção pequena e óbvia: pula.
- **Faço TDD?** Teste é obrigatório (está no DoD) e barato com IA. **Test-first** vale para lógica crítica/de negócio; **test-after** serve para UI e código de cola. Regra dura: a IA **nunca** apaga teste sem sua autorização. Chame de "TDD pragmático", não dogmático.
- **Separo por PRs?** Sim. 1 tarefa = 1 PR ≤ ~300 linhas, com fronteiras explícitas. PR gigante = revisão ruim = código ruim.
- **Chamo um orquestrador pra dar PRs aos agentes e validar?** O orquestrador é **você**. A IA não se autovalida. Você pode rodar 2-3 sessões em paralelo (supervisionar pelo `agent view`), mas o plano e o diff passam por você. Mais que 2-3 agentes: você vira o gargalo — não faça.
- **Como valido?** Três camadas: (a) gate automático — testes, lint, SAST; (b) sua revisão — no plano (barato, alto impacto) e no diff; (c) opcional — um agente revisor, segundo modelo com foco em segurança, tratando o código como input não-confiável.

## Anti-padrões (não faça)
- Swarm de 4-5 agentes autônomos. Você é o gargalo; 2-3 no máximo.
- `AGENTS.md` gigante. Regra demais dilui o contexto e a IA ignora.
- Perseguir token diretamente / gerar muito código. Menos código é melhor.
- Pular a revisão do plano. É o ponto onde você pega o erro mais barato.

---

# Parte 2 — Os documentos (o que entra em cada projeto)

## Mapa: arquivo → onde vai → quem lê

| Documento | Onde | Escopo | Quem lê |
|---|---|---|---|
| `project-template/AGENTS.md` + shim `CLAUDE.md` | raiz de cada repo | Por projeto | Agente, automático |
| `docs/security-DoD.md` | `docs/` de cada repo | Por projeto | Agente, sob demanda (banco/auth/input/pgto/mobile) |
| `docs/spec-template.md` | `docs/` de cada repo | Por projeto | **Você**, ao abrir feature |
| `docs/specs/<feature>.md` | `docs/specs/` | Por feature | Agente, no início da tarefa |

## Setup de QUALQUER projeto novo

**Em cada repo novo, no início:**
1. Copie `project-template/AGENTS.md` → `./AGENTS.md` e **preencha** (stack, restrições, convenções e segurança). Copie o shim `project-template/CLAUDE.md` → `./CLAUDE.md`.
2. Copie `docs/security-DoD.md` e `docs/spec-template.md` para `docs/`.

**Por feature (o que você entrega ao agente):**
3. Escreva a spec em `docs/specs/<feature>.md` (do template).
4. Aponte o agente para a spec e rode o fluxo spec-kit descrito acima.

## O que o agente recebe, em camadas
- **Sempre** (automático): `./AGENTS.md` do projeto e as instruções globais do executor usado.
- **Sob demanda**: `docs/security-DoD.md` quando a tarefa toca área sensível.
- **Por tarefa**: a spec da feature + os comandos do fluxo.

---

## Onde isto pode dar errado
- Isto é processo, não garantia. Ele reduz erro e desperdício; não elimina a sua responsabilidade de revisar.
- O overhead só compensa em trabalho que importa. Script descartável não precisa de spec/PRD.
- O harness mente se você não mantiver o contexto vivo. AGENTS.md desatualizado é pior que nenhum.
- Nada aqui está validado nos seus projetos ainda. Vira *seu* método quando sobreviver ao primeiro uso real.
