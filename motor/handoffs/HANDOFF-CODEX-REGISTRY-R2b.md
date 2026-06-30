# HANDOFF — Registry-cérebro, Corte R2b (Codex executa, Claude verifica)

> **Papéis:** Codex = EXECUTOR. Claude = VERIFICADOR. Spec travada. **Não relitigar.**
> Pré-requisito: R2a commitado (`capacidades_requeridas`, catálogo, seleção — 133 passed).
> Confira com `python3 -m pytest -q` antes de começar.

## Contexto

R2a deu ao motor o MECANISMO de seleção por capacidade+custo, mas ele só ativa quando
(a) as entidades do Registry declaram `capacidades` e (b) o subagente traz
`capacidades_requeridas`. R2b liga as duas pontas: **o planner passa a EMITIR
`capacidades_requeridas`**, e as entidades do Registry ganham as tags correspondentes.
Aí a fábrica escolhe o executor sozinha.

**Vocabulário FIXADO (5 tags cognitivas, decisão do Caio).** São capacidades do
*trabalho cognitivo*, ortogonais a `ferramentas` (que já tem mecanismo próprio) e
**domain-neutral de propósito**: valem pra software, hardware E manufatura, porque
qualquer domínio se decompõe nesse trabalho cognitivo ANTES de virar coisa física (a
produção física é de executores de DOMÍNIO, outro eixo, roteado depois pela biblioteca
de rotas / Curador — não é deste corte). As 5 tags, use EXATAMENTE estas palavras:

- `codigo` — escrever, editar ou revisar código/script (qualquer linguagem; inclui
  firmware, G-code, CAD-script).
- `redacao` — produzir texto em linguagem natural: relatório, documentação,
  especificação, descrição comercial.
- `calculo` — quantitativo determinístico: custos, tolerâncias, dimensionamento,
  projeções numéricas.
- `pesquisa` — levantar informação externa: busca, navegação, sourcing, lookup de
  normas/preços/concorrência.
- `raciocinio-longo` — planejamento, decomposição, trade-offs, design ou síntese
  multi-passo que exige modelo forte.

## Leis (não quebrar)

1. **1 corte = 1 commit** pequeno. Commitar ao fim.
2. **Nunca apagar nem afrouxar teste existente.** `python3 -m pytest -q` VERDE ao fim
   (hoje **133 passed**).
3. **Não tocar** no mecanismo do R2a (`selecionar_por_capacidade`, rung de `_resolver`,
   precedência pin>tier>capacidade>papel>padrão), nem na fronteira `cliente.chamar(...)`.
   R2b é: texto de prompt + frontmatter de entidades + 1 teste. NÃO mexe em lógica de
   roteamento.
4. **Ambiguidade não se chuta — para e anota** em `## DÚVIDAS`.
5. Python 3.14, só stdlib + deps do `pyproject.toml`. Sem dep nova.
6. Português, como o resto do repo.

---

## R2b — passos (FIXADOS)

### 1. `motor/grafo.py` — PROMPT_PLANNER emite capacidades_requeridas

No `PROMPT_PLANNER` (hoje termina no parágrafo do `tier`, logo antes de `{erro}`),
ADICIONE este parágrafo **literal**, mantendo o do tier (tier segue como hint de custo
grosso; capacidade é o sinal preciso — a precedência do R2a resolve qual tabela manda):

```
Para cada subagente, preencha também "capacidades_requeridas": a LISTA de capacidades que a tarefa exige, escolhidas SOMENTE deste vocabulário fixo (use exatamente estas palavras): codigo (escrever/editar/revisar código ou script), redacao (texto natural: relatório, doc, spec, descrição), calculo (quantitativo determinístico: custos, tolerâncias, dimensionamento), pesquisa (levantar info externa: busca, sourcing, lookup), raciocinio-longo (planejamento, trade-offs, design ou síntese multi-passo). Liste só o que a tarefa REALMENTE exige (em geral 1–2 tags). Estas tags valem para qualquer domínio (software, hardware, manufatura): a produção física é de outros executores; aqui você classifica só o trabalho cognitivo.
```

Não mude mais nada do prompt nem do nó `planner`. O campo `capacidades_requeridas` já
existe no schema (R2a) e já é passado pro grafo nas chamadas do executor — só falta o
planner preenchê-lo.

### 2. Entidades do Registry — tags + custo_ordem

As entidades de modelo-executor ganham `capacidades` (do vocabulário) e `custo_ordem`
(inteiro, ordem RELATIVA de custo — menor = mais barato; é um botão que o Caio/Curador
ajusta com telemetria, NÃO é $ literal). Edite/crie em `exemplos/registro-modelos/`:

**`claude.md`** (já existe; adicione as duas chaves ao frontmatter):
```yaml
capacidades: [codigo, redacao, calculo, pesquisa, raciocinio-longo]
custo_ordem: 10
```
(claude = juiz/fallback premium; cobre tudo, mas caro → só ganha quando nada mais barato cobre.)

**`codex.md`** (já existe; adicione):
```yaml
capacidades: [codigo, redacao, calculo, pesquisa, raciocinio-longo]
custo_ordem: 3
```
(codex = executor generalista agêntico, assinatura.)

**`qwen-coder.md`** (NOVO — coder barato especializado, demonstra a seleção):
```yaml
---
tipo: modelo-executor
transporte: opencode
provedor: oc
modelo: qwen/qwen3-coder
permissao: '{"edit":"deny","bash":"deny"}'
capacidades: [codigo]
custo_ordem: 1
---
Coder barato especializado (Qwen3-Coder via OpenCode). Só `codigo`, mas o mais barato —
ganha as tarefas de código sobre os generalistas. Auth: `opencode auth login`; confirme
o id exato com `opencode models` (ajuste `modelo:` se diferir de qwen/qwen3-coder).
```

Resultado esperado do catálogo: tarefa `codigo` → qwen (1) < codex (3) < claude (10) →
**qwen ganha**; `raciocinio-longo`/`pesquisa`/`redacao`/`calculo` → codex (3) < claude
(10) → codex; o que o codex não cobrir cai no claude; o verifier (evita o provedor do
executor) cai no claude. Isso EXERCITA o "coder barato a jusante, juiz premium".

### 3. Teste (tests/test_capacidade.py — adicione)

Carregue o catálogo REAL das fixtures e prove a seleção pelo vocabulário, sem CLIs reais
(`provedor_de` é puro):
```python
from motor.registro import cliente_de_registro
r = cliente_de_registro(<raiz>/"exemplos/registro-modelos")
assert r.provedor_de("x", capacidades=["codigo"]) == "oc"            # qwen, mais barato
assert r.provedor_de("x", capacidades=["raciocinio-longo"]) == "codex"
assert r.provedor_de("x", capacidades=["pesquisa","redacao"]) == "codex"
# verifier evitando o provedor do executor (codex) p/ raciocinio → claude
assert r.chamar("verifier","p", evitar="codex", capacidades=["raciocinio-longo"]) is not None
```
> Ajuste os provedores esperados se você renomear algo, mas mantenha a INTENÇÃO: código
> vai pro mais barato capaz; o resto pro generalista; juiz independente cai no padrão.

**NÃO** escreva teste que dependa da saída do planner LLM real (isso é calibração de run,
não unit test — fica com o Caio).

### DoD
1. `python3 -m pytest -q` verde (133 + os novos).
2. As 3 entidades têm `capacidades`+`custo_ordem`; `qwen-coder.md` criada.
3. PROMPT_PLANNER contém o parágrafo novo, com as 5 tags exatas.
4. Commit pequeno.

---

## Depois do R2b (com o Caio, NÃO neste handoff)

**Calibração em run real:** o Caio roda uma missão real e a gente olha se o planner
emite tags coerentes (saída de LLM é fuzzy — pode precisar afinar o parágrafo do prompt).
**Futuro:** `custo_max` por subagente (teto que força escalar em vez de pagar caro);
executores de DOMÍNIO físico (hardware/manufatura) como entidades com capacidades
próprias + biblioteca de rotas; o Curador ajustando `custo_ordem`/capacidades por
telemetria.

---

## DÚVIDAS
(Codex: escreva aqui o que travou, em vez de chutar.)
