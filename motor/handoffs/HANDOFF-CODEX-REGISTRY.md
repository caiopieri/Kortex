# HANDOFF — Registry-cérebro, Corte R1 (Codex executa, Claude verifica)

> **Papéis:** Codex = EXECUTOR (produz o código). Claude = VERIFICADOR (revisa o diff,
> roda a suíte, arruma). Este doc é a spec travada. **Não relitigar as decisões.**
> Spec à prova de executor potente: interface FIXADA, testes a montante como DoD,
> ambiguidade ESCALA (bloco `## DÚVIDAS` no fim — não chuta).

## Contexto (por que este corte existe)

Hoje o roteamento de modelos é 100% config JSON escrita à mão (`exemplos/modelos-*.json`,
lida por `cliente_de_config` em `motor/modelos.py`). O Registry do vault
(`4. Registry/`) já é o catálogo vivo da fábrica, mas só cataloga executores de
DOMÍNIO (redator, pesquisador-mercado). A pendência do kernel é: **os executores de
MODELO (claude, codex, opencode/qwen…) viram entidades do Registry, e o motor monta o
roteamento lendo o Registry em vez de JSON à mão.** Isso dá fonte-única-de-verdade,
fica visível no graph do Obsidian, é consultável pelo MCP, e é o que o Curador vai
ler/escrever no futuro.

**Tese travada (não mexer):** comprar a commodity, construir a diferenciação. O
`ClienteRoteador` (resolução pin > tier > papel > padrão, esgotado+cadeia, guard do
juiz) é a commodity TESTADA (118 passed) — **R1 NÃO toca nele**. R1 só adiciona um
LOADER novo que lê entidades `.md` e devolve exatamente o mesmo `ClienteRoteador` que
`cliente_de_config` devolveria. Trocamos a FONTE (JSON → Registry), não o motor.

## Leis (não quebrar)

1. **1 corte = 1 commit** pequeno (~≤300 linhas). Este handoff é só o R1.
2. **Nunca apagar nem afrouxar teste existente.** `python3 -m pytest -q` tem que ficar
   VERDE ao fim (hoje: **118 passed**). R1 é ADITIVO.
3. **Não tocar** `ClienteRoteador`, `cliente_de_config`, a fronteira
   `cliente.chamar(papel, prompt, ...)`, nem a semântica testada de
   tier/esgotado/pin/guard-do-juiz. R1 é um módulo NOVO + uma flag de CLI.
4. **Ambiguidade não se chuta — para e anota** em `## DÚVIDAS` e segue.
5. Python 3.14, **só stdlib** + o que já está no `pyproject.toml`. **Sem PyYAML nem
   dep nova** — escreve um parser de frontmatter mínimo pro schema fixo abaixo (ver
   "Parser"). Se julgar que precisa de YAML real, PARA e anota em DÚVIDAS.
6. Estilo: português nos comentários/docstrings, como o resto do repo.

## Mapa do código (contexto)

```
motor/modelos.py    ClienteModelo (Protocol) + ClienteStub + ClienteRoteador
                    + ClienteClaudeCLI + ClienteCodex + ClienteOpenCode
                    + ClienteOpenAICompat + cliente_de_config(cfg, log).
                    >>> R1 REUSA os 4 Cliente* de transporte e o ClienteRoteador.
                    >>> R1 NÃO edita este arquivo (só importa dele).
motor/__main__.py   CLI: --spec, --modelos, --esgotado, --auto, --gate, --pin, --caixa.
                    >>> R1 adiciona a flag --registro <pasta>.
motor/registro.py   <<< ARQUIVO NOVO que você cria neste corte.
tests/              pytest; ClienteStub determinístico. NÃO apagar.
```

Como `cliente_de_config` monta o `ClienteRoteador` (espelhe a MESMA forma):
- `padrao` = `ClienteClaudeCLI(log=log)`.
- `mapa`: papel → cliente (um cliente por provedor, compartilhado, com `mapa_papeis`).
- `tiers`: tier → cliente. Destino `"padrao"` referencia o `padrao` (claude).
- `cadeia`: lista dos clientes distintos não-padrao, ordem estável (fallback de esgotamento).
- Devolve `ClienteRoteador(padrao=…, mapa=…, tiers=…, cadeia=…, log=log)`.
- Segredo NUNCA no arquivo: openai-compat exige a chave via env (`api_key_env`); só
  provedor USADO exige chave.

---

## CORTE R1 — `cliente_de_registro(pasta, log=None)`

**Objetivo:** ler uma pasta de entidades `.md` (modelo-executor) e devolver um
`ClienteRoteador` equivalente ao que `cliente_de_config` devolveria para a config
JSON correspondente. **Mesma saída, fonte diferente.**

### Schema da entidade (FIXADO) — frontmatter YAML simples

Um arquivo `.md` por modelo-executor, frontmatter entre `---`. Campos:

```yaml
---
tipo: modelo-executor        # OBRIGATÓRIO; arquivos sem isto são IGNORADOS (não-modelo)
transporte: codex            # OBRIGATÓRIO: codex | opencode | openai-compat | claude-cli
provedor: codex              # rótulo de esgotamento; default = valor de `transporte`
modelo: default              # id do modelo; "provider/model" no opencode; "default"=padrão do CLI
padrao: false                # true SOMENTE no claude (o juiz/fallback). Default false.
papeis: [pesquisador, analista-custos]   # rota legada papel→este modelo (opcional)
tiers: [simples, media]      # tiers que ESTE modelo atende (opcional)
# --- só openai-compat ---
base_url: https://...        # obrigatório se transporte=openai-compat
api_key_env: NOME_DA_VAR     # obrigatório se transporte=openai-compat (chave via env)
# --- só codex (opcionais) ---
sandbox: read-only           # default read-only
search: false                # default false
# --- só opencode (opcional) ---
permissao: '{"edit":"deny","bash":"deny"}'
# --- ignorados por R1, reservados pro R2 (auto-seleção por capacidade+custo) ---
capacidades: [código, ferramentas]
custo_ordem: 0
custo: "$0 (assinatura)"
---
Prosa livre + [[links]] (o graph view do Obsidian renderiza de graça).
```

### Regras de montagem (FIXADAS)

1. **Varre `pasta`** (não-recursivo basta; se quiser recursivo, tudo bem) por `.md`.
   Arquivo sem `tipo: modelo-executor` no frontmatter → **ignora** (deixa conviver com
   notas/índices na mesma pasta).
2. **`padrao`**: a entidade com `padrao: true` define o cliente padrão. Construção do
   padrão = `ClienteClaudeCLI(log=log)` (transporte `claude-cli`). 
   - **0 entidades padrão** → usa `ClienteClaudeCLI(log=log)` (comportamento de hoje).
   - **>1 entidade padrão** → `ValueError` (ambiguidade não se chuta).
3. **Um cliente por entidade** (exceto a padrão, que É o `padrao`), construído pelo
   transporte declarado, reusando os `Cliente*` de `modelos.py`:
   - `codex` → `ClienteCodex(modelo=…, sandbox=…, busca_ao_vivo=search, log=log)`
   - `opencode` → `ClienteOpenCode(modelo=…, permissao=…, log=log, provedor=provedor)`
   - `openai-compat` → `ClienteOpenAICompat(base_url=…, api_key=<env>, modelo=…, log=log, provedor=provedor)`
   - `claude-cli` (não-padrão, raro) → `ClienteClaudeCLI(log=log)`
   - `modelo` ausente/"default" segue a mesma semântica dos `Cliente*` (vira `None`/CLI default).
4. **`mapa`**: para cada papel listado em `papeis` de uma entidade, `mapa[papel] = cliente_da_entidade`.
5. **`tiers`**: para cada tier listado em `tiers` de uma entidade, `tiers[tier] = cliente_da_entidade`.
   - Uma entidade pode declarar `padrao: true` E tiers — nesse caso o tier mapeia pro `padrao`.
6. **Conflito = erro, nunca silêncio:** se duas entidades reivindicam o MESMO papel, ou
   o MESMO tier → `ValueError` com o nome dos dois arquivos. Roteamento ambíguo tem que
   ser explícito (o Caio resolve editando o Registry).
7. **`cadeia`**: clientes distintos não-padrao, ordem estável (ordene por nome de
   arquivo pra ser determinístico), sem duplicar por identidade — igual `cliente_de_config`.
8. **Segredo via env:** `openai-compat` com `api_key_env` cuja env está vazia E o
   provedor é efetivamente usado → `ValueError` (mesma regra de `cliente_de_config`;
   reaproveite a mensagem "exporte a chave; ela nunca vai no arquivo").
9. **pins e esgotados NÃO vêm do Registry** neste corte — continuam runtime (CLI
   `--pin`, `--esgotado`, e o `~/.motor/pins.json` global). O Registry define o
   CATÁLOGO (quais modelos existem + bindings papel/tier default); overrides de
   execução ficam na CLI. Não invente campos de pin/esgotado na entidade.

### Parser de frontmatter (stdlib, escopo do schema)

Escreve um parser mínimo (sem PyYAML). Aceita:
- bloco entre a 1ª e a 2ª linha `---`;
- `chave: valor` escalar (string; trim de aspas simples/duplas se houver);
- `chave: true|false` → bool; `chave: <int>` → int;
- `chave: [a, b, c]` lista flow (split por vírgula, trim) — pode ter colchete vazio `[]`;
- linhas em branco e o corpo após o 2º `---` são ignorados.
Não precisa suportar listas em bloco (`- item`), aninhamento, nem multilinha. Se uma
entidade real precisar disso, é outro corte — anota em DÚVIDAS.

### Fixtures (você cria, fazem parte do DoD)

Crie `exemplos/registro-modelos/` espelhando **exatamente** `exemplos/modelos-codex.json`:
- `claude.md` → `tipo: modelo-executor, transporte: claude-cli, padrao: true, tiers: [complexa]`
- `codex.md` → `tipo: modelo-executor, transporte: codex, modelo: default, tiers: [simples, media], papeis: [pesquisador, analista-custos, modelador-dados]`
- (opcional) um `_indice.md` SEM `tipo: modelo-executor` pra provar que arquivos
  não-modelo são ignorados.

### CLI

Em `motor/__main__.py`: flag `--registro <pasta>` que monta o cliente via
`cliente_de_registro`. `--registro` e `--modelos` são ALTERNATIVAS — se ambas forem
passadas, erro claro ("use --registro OU --modelos, não os dois"). Sem nenhuma,
comportamento de hoje (claude puro).

### DoD (tests/test_registro.py)

1. **Equivalência:** `cliente_de_registro("exemplos/registro-modelos")` e
   `cliente_de_config(<json equivalente ao modelos-codex.json>)` produzem o MESMO
   roteamento. Teste com `provedor_de(papel, tier)` numa matriz de sondas:
   `("pesquisador", None)`, `(qualquer, "simples")`, `(qualquer, "media")`,
   `(qualquer, "complexa")`, `("synthesizer", None)` → mesmos provedores nos dois.
2. **Conflito de tier** entre duas entidades → `ValueError`.
3. **>1 padrão** → `ValueError`; **0 padrão** → cai em `ClienteClaudeCLI`
   (`provedor_de("qualquer", None) == "claude"`).
4. **Arquivo sem `tipo: modelo-executor`** é ignorado (não vira cliente nem quebra).
5. **openai-compat com env vazia, provedor usado** → `ValueError` (use
   `monkeypatch.delenv(..., raising=False)`).
6. Suíte verde (118 + os novos).

> Use `ClienteStub` onde der pra não depender dos CLIs reais. Para a matriz de sondas,
> `provedor_de` é puro (não executa modelo) — perfeito pro teste.

---

## FUTURO — Corte R2 (NÃO fazer agora; design pendente com o Claude)

**Auto-seleção por capacidade + custo.** Hoje (e no R1) o binding é manual: a entidade
declara QUAIS papéis/tiers ela atende. No R2 inverte: o planner declara, por subagente,
as `capacidades_requeridas` + um teto de custo (ou reusa o tier como teto); um resolver
novo consulta o catálogo e escolhe **o executor mais barato cujas `capacidades` cobrem
o requisito** (`custo_ordem` mínimo entre os capazes); nenhum capaz → escala (evento
`registro.sem_executor`, cai no padrão), NUNCA escolhe modelo incapaz em silêncio. O
guard de independência do juiz tem que continuar valendo (verifier ≠ provedor do
executor). Isso alimenta o **Curador** (telemetria → propor entidades novas / ajustar
`custo_ordem`). R2 mexe no prompt do planner + no schema da spec → exige decisão de
arquitetura, fica pro Claude a montante. **Não improvise R2 aqui.**

---

## DÚVIDAS
(Codex: escreva aqui o que travou, em vez de chutar.)
