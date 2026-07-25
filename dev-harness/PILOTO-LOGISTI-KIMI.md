# Piloto Logisti — Rota Forja sob regime barato (Kimi K2.6)

> Objetivo do piloto: certificar a rota spec-kit (L0 → L1) rodando o executor
> inteiro no Kimi K2.6 via proxy. Se passar, certifica rota E regime barato de uma vez.
> Claude premium: SÓ na revisão do plano (opcional, ~minutos de token — colar o plano
> na sessão Cowork do Claude).

## 0. Pré-voo (terminal normal, sem IA)

```bash
mkdir -p ~/Desktop/Projects/logisti && cd ~/Desktop/Projects/logisti && git init

# spec-kit (se ainda não instalou a CLI)
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
specify init . --integration claude

# camada do harness que o spec-kit vanilla NÃO tem — contexto permanente do projeto
cp ~/Desktop/Projects/Orquestrador/dev-harness/project-template/AGENTS.md .
cp ~/Desktop/Projects/Orquestrador/dev-harness/project-template/CLAUDE.md .
# → preencha o AGENTS.md (o quê/stack/comandos do Logisti) ANTES de abrir o agente

# conferir que o núcleo universal está instalado (vale p/ todos os projetos)
ls ~/.claude/CLAUDE.md || cp ~/Desktop/Projects/Orquestrador/dev-harness/global/CLAUDE.md ~/.claude/CLAUDE.md
```

Abrir o Claude Code apontado para o SEU proxy Kimi (a mesma forma que você já usa;
genericamente):

```bash
export ANTHROPIC_BASE_URL=<url-do-seu-proxy>
export ANTHROPIC_API_KEY=<chave-do-proxy>
claude
```

Sanidade: pergunte "que modelo você é?" — confirme que respondeu como Kimi/proxy
antes de gastar qualquer comando.

## 1. Constitution (1ª coisa dentro do Claude Code)

```
/speckit.constitution
```

Cole o conteúdo da seção 3 de `spec-kit-adocao.md` (Princípios I–VI + Security +
Governance). Sem constitution, nada do resto referencia as regras.

## 2. Discovery (você + Kimi, mas a decisão é sua)

Copie `dev-harness/docs/discovery-template.md` para o repo e preencha:
dor, hipótese arriscada, menor teste que invalida, TIER (sugestão: T1), fora-de-escopo.
Pode pedir ao Kimi para rascunhar, mas VOCÊ fecha o documento.

Depois: `ROADMAP.md` (template em docs/) — 1 fatia em "Now". Fatia pequena:
o piloto certifica a rota, não entrega o produto inteiro.

## 3. O ciclo spec-kit (uma fatia)

| # | Comando | Gate | Telemetria (anotar) |
|---|---|---|---|
| 1 | `/speckit.specify <fatia>` | — | modelo, tempo, retrabalho? |
| 2 | `/speckit.clarify` | responda as perguntas | idem |
| 3 | `/speckit.plan` | **VOCÊ revisa o plano. Parada obrigatória.** (opcional: colar no Claude/Cowork p/ review premium) | idem |
| 4 | `/speckit.tasks` | — | idem |
| 5 | `/speckit.analyze` | inconsistência P1 = volta ao plan | idem |
| 6 | `/speckit.checklist` | T1+: qualidade da spec | idem |
| 7 | `/speckit.implement` | testes locais passam | idem + nº de iterações |
| 8 | commit + **VOCÊ revisa o diff** | **Parada obrigatória.** | idem |

Prompt de abertura sugerido para o passo 1 (ajuste a fatia):

```
/speckit.specify Construa a primeira fatia do Logisti conforme docs/discovery.md e
ROADMAP.md (fatia "Now"). Tier T1. Executor desta sessão é um modelo de tier barato:
siga o PRINCÍPIO VI da constitution — não tome decisões de design implícitas; em
ambiguidade, pergunte. Não toque em arquivos fora do escopo da fatia.
```

## 4. Regras do piloto (não relaxar)

- Kimi falhou 2-3x na mesma tarefa do implement → anote e escale a TAREFA (não a
  sessão) para Sonnet semana que vem; siga com as demais.
- NUNCA deixar o Kimi editar testes para passar. Teste "errado" = parar e reportar.
- Cada fase: anotar na telemetria (modelo=kimi-k2.6, tempo, retrabalho, onde o gate pegou erro).
- Guardar TODOS os artefatos intermediários (spec.md, plan.md, tasks.md) commitados —
  permite re-rodar UMA fase com Claude depois para isolar falha.

## 5. Kill criteria (mesmos do finance-sim — comparar com a baseline)

1. Menos retrabalho do que sem harness? (baseline: finance-sim disse "sim")
2. O gate do plano pegou mais erro que o do diff? (baseline: sim)
3. A fatia saiu funcionando com testes no caminho crítico?

Passou os 3 → Rota Forja sobe a L1 (anotar: "certificada sob regime barato/kimi-k2.6").
Falhou → registrar QUAL fase falhou e re-rodar só ela com Claude antes de culpar a rota.
