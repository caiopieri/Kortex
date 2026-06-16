# Runbook — 1º golden run do motor com Codex (executor) + Claude (verificador)

Objetivo deste run: **ver os nós acenderem no painel** com o Codex executando os
subagentes e o Claude julgando (verifier/evaluator). Não é entregar feature — é
provar a automação ponta a ponta com as duas assinaturas, separadas por papel.

Tudo aqui roda no **teu Mac** (o sandbox Linux não tem `codex`/`claude` com as tuas
assinaturas). O wiring (ClienteCodex + config + specs + testes) já está pronto e
**74/74 testes passam**.

## Mapa de papéis (travado)

- **Codex = executor**: papéis de subagente (`pesquisador`, `analista-custos`,
  `modelador-dados`) — alto volume. Via `codex exec`, assinatura ChatGPT, sem chave de API.
- **Claude = julgamento**: `planner`, `verifier`, `evaluator`, `synthesizer` ficam
  no padrão (`claude -p`). Cross-model anti-viés de auto-preferência (lei do harness).
- **Ferramentas ficam COM o Codex** (ele é agêntico: web search, leitura de arquivos,
  MCP). Papel com `ferramentas: WebSearch` → `codex exec --search` (busca ao vivo).
  Sandbox default = `read-only` (nó é texto-entra/texto-sai; não mexe no repo). Pra um
  executor que EDITA código, põe `"sandbox": "workspace-write"` no provedor codex da config.

## Pré-requisitos (uma vez)

```bash
cd ~/Desktop/Projects/Orquestrador/motor
source .venv/bin/activate
python -m pytest -q          # esperado: 74 passed (confirma o wiring)

# Codex CLI instalado e logado na tua conta ChatGPT:
codex --version
codex login                  # se ainda não logou neste Mac
# claude CLI já logado (mesmo do uso normal):
claude --version
```

### Smoke do Codex isolado (10s — confirma que o CLI responde)

```bash
codex exec --skip-git-repo-check --ephemeral "responda apenas: ok"
```

Tem que imprimir a mensagem final no stdout. Se isto falhar, o problema é o Codex CLI,
não o motor — resolve aqui antes de seguir.

## Run 1 — SMOKE do wiring (spec que já existe, menor superfície de atrito)

Roteia o papel `pesquisador` ao Codex; planner/verifier/evaluator/synthesizer no Claude.

**Terminal A — painel** (deixa aberto):
```bash
cd ~/Desktop/Projects/Orquestrador/motor && source .venv/bin/activate
python3 motor_painel/painel.py      # → http://localhost:8378
```

**Terminal B — motor**:
```bash
cd ~/Desktop/Projects/Orquestrador/motor && source .venv/bin/activate
python -m motor --spec exemplos/missao-pesquisa.json --modelos exemplos/modelos-codex.json
```

Abre http://localhost:8378 e recarrega enquanto roda. O que **deve** acontecer:

1. Nó `planner` acende (Claude monta a spec).
2. Dois subagentes `pesquisa-alfa`/`pesquisa-beta` (papel `pesquisador`) acendem em
   paralelo — esses são o **Codex**.
3. Cada um passa por `verifier:<id>` (Claude) → aprovado/reprovado (retry ≤ 3).
4. `global_evaluator` (Claude) → `synthesizer` (Claude) → relatório final no stdout.

No `log.jsonl` (raiz do repo) confirma a separação por papel — procura `executor.chamado`
com `papel: pesquisador` (Codex) e os `portao.*` do verifier (Claude).

## Run 2 — fatia pequena do Logisti (custos por caminhão)

Só depois do Run 1 limpo. Mesma config; a spec é um **artefato de planejamento** da
fatia 2 (não código aplicado — é entrada para um `/speckit.specify` depois). Papéis
executores `analista-custos` e `modelador-dados` → Codex.

```bash
python -m motor --spec exemplos/logisti-fatia2.json --modelos exemplos/modelos-codex.json
```

Saída = mini-spec da fatia 2 (categorias de custo + modelo de dados encaixado na
fatia 1 + consulta de custo por caminhão/período). Revisa o artefato; se servir,
vira a base do specify da fatia 2.

## Quando um modelo acaba (Corte B — disponibilidade)

Se o limite do Claude (ou de qualquer provedor) acabar no meio, marca ele como
esgotado e o motor reroteia o que iria pra ele — inclusive o julgamento
(verifier/evaluator/synthesizer) — pro fallback, em vez de pendurar:

```bash
python3 -m motor --spec exemplos/logisti-fatia2.json --modelos exemplos/modelos-codex.json --esgotado claude
```

Isso é o que mata o travamento do synthesizer: com `claude` esgotado, a síntese
sai no Codex. `--esgotado` é repetível (`--esgotado claude --esgotado nvidia`).
Também dá pra fixar no JSON da config: `"esgotados": ["claude"]`. No log vais ver
`modelo.reroteado_esgotado` (de→para) por tarefa reroteada.

## Auto-mode: quanto o motor te interrompe (Corte C)

Por padrão, quando a cobertura fica insuficiente o motor PAUSA e te pergunta
(prosseguir/abortar). Com auto-mode ele resolve sozinho e segue:

```bash
python3 -m motor --spec exemplos/logisti-fatia2.json --modelos exemplos/modelos-codex.json --auto
```

Exceção por gate (tudo auto, MENOS um): `--auto --gate cobertura=manual`.
Automatizar só um gate sem ligar o master: `--gate cobertura=prosseguir` (ou
`=abortar`). Também dá pra fixar no JSON: `"politica_gates": {"auto_mode": true,
"gates": {"cobertura": "manual"}}`. No log: `gate.auto` (resolveu sozinho) vs
`escalado`+`decisao.fundador` (pausou e perguntou).

> Nota: o gate de cobertura só dispara DEPOIS das retentativas do verifier
> esgotarem. "Prosseguir" = sintetizar com o que passou; "abortar" = encerrar.
> (Uma 3ª opção "preencher a lacuna" — re-fan-out pro buraco — é candidata futura.)

## Três executores + pins manuais

Além de Codex e Claude, há o **OpenCode** (`tipo: opencode`) pros outros modelos —
inclusive GPT-5.5 pago-por-token quando tu não estiver no Codex. Auth:
`opencode auth login` (sem chave no nosso arquivo). Exemplo: `exemplos/modelos-opencode.json`.

**Pins** = fixar manualmente um modelo, com precedência sobre o planner ("não me
questiona"). Chave = papel, tier ou `"*"` (tudo). Três jeitos:

- No JSON do projeto: `"pins": {"synthesizer": "oc/openai/gpt-5.5"}`.
- Ad-hoc na linha: `--pin synthesizer=oc/openai/gpt-5.5` (repetível).
- Global, todos os projetos: `~/.motor/pins.json` (mesma forma; o projeto sobrepõe).

Precedência geral: **pin (papel > tier > `*`) > tier > papel > padrão**, e o
esgotamento (Corte B) ainda reroteia se o provedor pinado cair. Log: `modelo.pin`.

## Ver os dois painéis (o teu e o do LangGraph)

São **dois servidores/visões separadas**, podem rodar ao mesmo tempo:

- **Teu painel** (mapa orbital, lê `log.jsonl`): roda uma missão pela CLI
  (`python3 -m motor ...` — é o que escreve o `log.jsonl`), depois
  `python3 motor_painel/painel.py` → http://localhost:8378.
- **LangGraph Studio**: `langgraph dev` → abre no browser; as runs tu inicia
  DENTRO do Studio (painel Interact).

Nuance importante: o `motor/studio.py` usa um log no-op (pra não travar o event
loop do Studio), então **runs feitas no Studio NÃO aparecem no teu painel** e
vice-versa. Teu painel = runs da CLI; Studio = runs do Studio. Se um dia quiser
unificar, é fazer o studio.py escrever o `log.jsonl` (de forma assíncrona).

## Independência do juiz (cross-model)

Automático: o verifier de cada subagente nunca roda no mesmo provedor do executor
que ele julga (senão o modelo se auto-aprova). Se o roteamento/esgotamento tentar
colapsar os dois no mesmo provedor, o motor desvia o juiz e loga `juiz.independencia`.
Um PIN explícito teu no verifier vence o guard (tua decisão consciente).

## Critérios de falsificação (anota o veredito)

1. **Separação de papéis real**: no `log.jsonl`, subagentes saíram do Codex e os
   portões do Claude? (não pode haver verifier rodando no Codex).
2. **Painel ao vivo**: os nós dinâmicos da spec apareceram e mudaram de estado?
3. **Resiliência**: se o Codex falhar/timeout num nó, viu `modelo.falha` e o fallback
   ao Claude no log — em vez de a missão morrer silenciosa?

## Atrito esperado (não é bug)

- **Timeout**: `codex exec` é agêntico e pode passar dos 300s/nó. Se um nó estourar,
  ele retenta e cai pro Claude. Pro smoke (pesquisa, sem ferramenta) deve fechar rápido.
- **Input inchado** (diagnosticado, NÃO consertado ainda): implement agêntico queima
  input. Estas specs são leves (planejamento), então não morde aqui — o conserto
  (escopo curto/nó, contrato compacto da fundação, commit entre fases) é trabalho à parte.

## Ao terminar

```bash
git add -A && git commit -m "feat: ClienteCodex (executor) + config tipo:codex + specs do golden run (74/74)"
```

(O `log.jsonl` da raiz é o log VIVO — não commitar; a amostra do painel é
`exemplos/log-amostra.jsonl`.)
