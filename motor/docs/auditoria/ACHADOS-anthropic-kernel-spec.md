# ACHADOS — auditoria de kernel (K1–K4) e spec/capacidades (S1–S5)

Auditor: revisão defensiva independente. Escopo: `motor/spec.py`, `motor/politica.py`,
`motor/grafo.py` (`construir_grafo` e nós), confrontados com `docs/INVARIANTES.md`.

**Baseline:** `.venv/bin/python3 -m pytest -q` → **972 passed, 7 skipped** (170s). A suíte
está verde e continua verde com todos os achados abaixo presentes — ou seja, ela não mede
essas promessas.

**Probes:** `motor/tests/test_auditoria_anthropic_kernel_spec.py` — 6 testes, **6 falham**
contra o código atual. Cada achado abaixo referencia o seu. Nenhum código de produção foi
alterado.

Resumo: **2 🔴 · 3 🟡 · 3 🟢**

---

## 🔴 A1 — O `nos_a_refazer` do evaluator é descartado sempre que existe algum subagente reprovado (K3, S2, G2)

**Onde:** `motor/motor/grafo.py:1147-1154`

```python
if reprovados:
    veredito = {"aprovado": False,
                "lacunas": list(veredito.get("lacunas", [])) + [...]}   # <- dict RECONSTRUÍDO
nomes = veredito.get("nos_a_refazer", [])   # <- agora sempre []
```

O veredito tipado é **substituído** por um dict novo que não carrega `nos_a_refazer`.
A linha seguinte lê `nos_a_refazer` desse dict já mutilado, então a atribuição de culpa
feita pelo evaluator (o nó **a montante** responsável pela lacuna) é silenciosamente
perdida. Sobra apenas `refazer_reprovados`, que é a lista dos nós que já falharam sozinhos.

Consequência: exatamente no cenário em que a reconciliação mais importa — algo reprovou
**e** o evaluator sabe que a origem real está mais acima — o motor refaz só o sintoma,
nunca a causa. O invariante G2 ("aponta o nó culpado ... refaz ele e seus dependentes")
vale apenas quando **nada** reprovou; e nesse caso não havia culpado a apontar.

**Por que a suíte não pega:** `test_grafo.py:492` (`test_gate_cobertura_preencher_refaz_fonte_e_dependentes_em_ordem`),
o teste citado no INVARIANTES como prova de G2, monta um cenário em que **todos os
subagentes aprovam no verifier** e só o evaluator reprova. É precisamente o único ramo em
que `reprovados` é vazio e o bug fica dormente. O teste passa por acidente de cenário: ele
não exercita o caminho `if reprovados:`, que é o caminho de produção mais comum.

**Prova:** `tests/test_auditoria_anthropic_kernel_spec.py::test_A1_nos_a_refazer_do_evaluator_sao_descartados_quando_ha_reprovado`

```
AssertionError: evaluator apontou 'A' como origem, mas a reconciliação cobriu ['C']
assert {'C'} == {'A', 'B', 'C'}
```

---

## 🔴 A2 — Spec fornecida pelo usuário escapa completamente do teto bootstrap (S4, S5, K1)

**Onde:** `motor/motor/grafo.py:497-500` (caminho da spec fornecida) vs. `grafo.py:539`
(caminho gerado pelo planner)

```python
if state.get("spec"):
    spec = WorkflowSpec.model_validate(state["spec"])   # nenhuma confrontação com teto_bootstrap
    ...
    return {"spec": spec.model_dump(), "run_id": run_id}
...
# só no ramo gerado:
if Decimal(str(spec.restricoes.teto_custo)) > teto_bootstrap:
    raise ValueError("spec gerada nao pode elevar teto bootstrap")
```

Todo gasto de executor/verifier/evaluator/synthesizer abre sessão de orçamento com
`spec["restricoes"]["teto_custo"]` (`grafo.py:705, 733, 1130, 1331`). `Restricoes.teto_custo`
(`spec.py:78`) é `> 0` e finito, **sem limite superior**. Logo, uma spec entregue pela CLI
ou pelo serviço — o entrypoint de produção primário, e o que K1 declara suportado —
autoriza a si mesma um teto arbitrário. O `teto_bootstrap`, que S5 descreve como
"configuração decimal obrigatória", governa só a sessão do planner e a spec que ele gera.

O contêiner monetário fail-closed do motor é, na prática, um contêiner sobre o texto
gerado pelo LLM, não sobre a execução.

**Por que a suíte não pega:** `tests/test_hardening_h12b4d_grafo.py:39-67` normaliza o
padrão — `_spec(teto=...)` injeta teto arbitrário em spec do usuário e `_invocar` nem passa
`teto_bootstrap`. A família de testes S4/S5 testa se o teto **da spec** é respeitado; nenhum
teste pergunta de onde veio a autoridade daquele teto.

**Prova:** `...::test_A2_spec_do_usuario_pode_elevar_teto_acima_do_bootstrap`

```
AssertionError: spec do usuário abriu sessão de orçamento com teto 1000000.0 > bootstrap 2.0
```

(Todas as 6+ sessões abertas no run usaram `Decimal('1000000.0')`.)

---

## 🟡 A3 — Rubrica e critérios de cobertura em branco passam na validação (K3, S1)

**Onde:** `motor/motor/spec.py:96` (`rubrica: list[str]`), `spec.py:125`
(`criterios_cobertura: list[str]`), checagem em `spec.py:158-159`

O módulo define `NonBlank` (`spec.py:14`) e o usa em `ConfigContem.requer` e em
`capacidades_requeridas` — mas **não** na rubrica nem nos critérios de cobertura. A
checagem é `if not s.rubrica`, ou seja, apenas "lista não vazia".

Resultado: `rubrica: ["", "   "]` é uma spec válida. O portão verifier então roda
(`grafo.py:734-739`) com a rubrica renderizada como `- ` / `-   ` e é instruído a "aprovar
se TODOS os critérios da rubrica forem atendidos" — o que é vacuamente verdadeiro. K3
("nada cruza fronteira sem portão") passa a valer sintaticamente e falhar semanticamente.
Idem para `criterios_cobertura: ["  "]` e o gate de cobertura.

Não é hipotético: o planner é um LLM sob prompt (`grafo.py:143-150`) que pode emitir
strings vazias, e o único filtro entre ele e a execução é este validador.

**Prova:** `...::test_A3_rubrica_e_criterios_em_branco_passam_na_validacao` → `DID NOT RAISE`.

---

## 🟡 A4 — `validador`/`valida` em nó tipo `modelo` é aceito e nunca executado (S1, S2, K3)

**Onde:** `motor/motor/spec.py:154-172` (checagens condicionadas a `s.tipo == "validador"`),
`grafo.py:635-640` (dispatch por tipo)

Todas as regras de integridade de validador — alvo existente, alvo em `depende_de`, não
auto-validação, `validador` presente — só rodam quando `tipo == "validador"`. Um nó
`tipo: "modelo"` pode declarar `validador: {...}` e `valida: "id-que-nao-existe"`; a spec
valida sem erro. Em runtime, `subagente()` cai no ramo de modelo e o validador declarado
**nunca é executado**, sem exceção, sem evento, sem `validador.rodou`.

Isto é dívida silenciosa na direção mais perigosa: o autor da spec (humano ou planner)
acredita ter instalado um portão determinístico e o motor não instalou nada. S2 ("validador
sempre aponta alvo existente e dependente") é verdadeiro só para nós que já se declararam
validadores — a condição é auto-referente.

Correção mínima esperada: rejeitar `validador`/`valida` em `tipo != "validador"`.

**Prova:** `...::test_A4_validador_declarado_em_no_modelo_e_silenciosamente_ignorado` → `DID NOT RAISE`.

---

## 🟡 A5 — Fallback sem `jsonschema` enfraquece o portão `schema_json` silenciosamente (K3, S1)

**Onde:** `motor/motor/grafo.py:52-57`, `247-292`, `303-316`; `pyproject.toml`

`jsonschema` é importado sob `try/except ImportError` e **não está declarado em
`pyproject.toml`** (está presente no `.venv` apenas como dependência transitiva). Quando
ausente, o motor cai em `_validar_schema_minimo`, que implementa somente `type`, `required`,
`properties`, `additionalProperties` e `items` — ignora `enum`, `minimum`/`maximum`,
`pattern`, `format`, `oneOf`/`anyOf`/`allOf`, `uniqueItems`, `minLength`.

Os dois modos devolvem a **mesma** string `"schema_json aprovado"` e o mesmo evento
`validador.rodou` com `aprovado=True`. Não existe evento, campo ou log que permita a um
auditor distinguir "aprovado por JSON Schema" de "aprovado pelo subconjunto". A mesma spec
tem força de portão diferente conforme o ambiente de deploy — e o ambiente de deploy não é
pinado.

**Prova:** `...::test_A6_fallback_sem_jsonschema_enfraquece_o_portao_silenciosamente`

```
AssertionError: sem jsonschema o mesmo payload é aprovado (schema_json aprovado);
o portão depende de uma dependência não declarada
```

(payload `{"status": "INVENTADO", "n": 1}` contra `enum: ["ok","erro"]` + `minimum: 10`.)

---

## 🟢 A6 — Runtime do validador `contem` aceita `min: 0`, que a spec proíbe (S1)

**Onde:** `motor/motor/grafo.py:325-328` vs. `motor/motor/spec.py:30-40`

`ConfigContem.minimo` é `InteiroPositivo` (`ge=1`) e rejeita `min > len(requer)`. O runtime
faz `minimo = max(0, min(minimo, len(requer)))`, então `min: 0` vira aprovação
incondicional (`len(presentes) >= 0`) em vez de erro. `_validar_contem` recebe um dict
cru e reimplementa uma política de coerção **mais permissiva** que o contrato tipado.

Severidade baixa porque não há caminho conhecido em que o dict chegue ao runtime sem passar
por `ConfigContem` (`WorkflowSpec.model_dump()` preserva os aliases corretamente —
verificado com pydantic 2.13.4). Mas é uma divergência real entre o contrato e o
enforcement: se algum dia um dict de config chegar por outra via (edição de spec no gate,
projeção, replay), o portão silenciosamente aprova tudo.

**Prova:** `...::test_A5_runtime_do_contem_aceita_min_zero_que_a_spec_proibe`

---

## 🟢 A7 — `grafo_dep.travado` deixa nós sem resultado, invisíveis ao gate de cobertura

**Onde:** `motor/motor/grafo.py:1064-1066` e `1214-1216`

Quando uma onda fica vazia, o laço faz `break` e retorna resultados parciais. Os nós
restantes **não** produzem entrada em `resultados`, então `avaliar_cobertura` (`grafo.py:1120`)
não os enxerga como reprovados — sua ausência só seria percebida pelo evaluator LLM.

Hoje é código defensivo morto: `WorkflowSpec._consistencia` garante DAG e ids existentes, e
`resultado_bloqueado` sempre commita um resultado mesmo para nó bloqueado, então a onda vazia
é inalcançável. Registrado como fragilidade estrutural: o fail-closed do laço é um `break`
silencioso, não um abort. Um `abortada=True` seria o comportamento consistente com K3.

---

## 🟢 A8 — `revisar_plano` trata qualquer `resume` do tipo dict como edição de tier

**Onde:** `motor/motor/grafo.py:585-599`

Todo `Command(resume=<dict>)` é interpretado como mapa `id_do_subagente → tier`. Um humano
(ou um cliente do serviço) que responda `{"decisao": "abortar"}` recebe
`ValueError: edicao referencia subagente desconhecido` — exceção **não capturada**, que
derruba o nó em vez de virar decisão inválida/abortada, como faz o ramo de string
(`grafo.py:607`). Tratamento de erro parcial: o mesmo gate tem duas disciplinas de falha.

---

## Áreas onde NÃO encontrei nada de severidade ≥ média

Declarado explicitamente, para que silêncio não seja lido como aprovação:

- **K4 / U3 — `preparar_promocao_gated` (`curador.py:354-415`).** Correto e genuinamente
  fail-closed: sem `repositorio`, sem `certification_id` string não-vazia, com registro
  inconsistente ou com `decisao != recomputada`, sempre `promocao_vetada`. O registro é
  `deepcopy`ado antes de qualquer leitura e a decisão é **recomputada** de `certificar_sombra`
  — dict/JSON externo não tem autoridade. Só emite `curador.promocao_pendente` com
  `requer_gate=True`; não existe caminho de apply. Sem achado.
- **`politica.py` (K/F3).** `GATES_SENSIVEIS` é consultado **antes** de override e de
  `auto_mode` (`politica.py:56`), então `promocao`/`autorizacao`/`risco`/`dinheiro` não são
  auto-respondíveis por nenhum caminho, inclusive default injetado pelo chamador. Gate
  desconhecido → `None` → manual. `politica_de_config` valida tipos e delega ao
  `__post_init__`. Tentei quebrar por mutação pós-construção de `overrides` (dataclass
  mutável) e o guard sensível ainda segura. Sem achado.
- **S3 — enforcement de capacidade.** `grafo.py:640-648` bloqueia fail-closed cliente sem
  `roteamento_capacidades_runtime`, emite `registro.sem_executor` + `executor.erro` e commita
  resultado reprovado. `[]`/ausente preserva rota legada, como o invariante promete. Os
  testes `test_hardening_h12a.py` exercitam pin/tier/fallback de verdade (não monkeypatcham
  o roteador). Sem achado.
- **Serialização de aliases da spec.** Verifiquei explicitamente com pydantic 2.13.4 que
  `WorkflowSpec.model_dump()` emite `config.schema` e `config.min` (aliases), que é o que o
  runtime lê. Não há divergência dump↔runtime. Sem achado.
- **Identidade de reserva sob retry/failover (S4).** `call_id`/`reservation_id`
  (`grafo.py:449-462`) incorporam `run_id`, `thread_id`, `fase`, `no_id`, `ciclo`, `tentativa`
  e `route_id`; a unicidade no banco é `(run_id, thread_id, call_id, route_id, attempt)`
  (`orcamento.py:600`). O `call_id` curto do planner (`planner-{fase}-{tentativa}`) **não**
  colide entre runs por causa dessa chave composta. Sem achado.
- **Concorrência do fan-out.** Ramos `Send` concorrentes reduzem por `mesclar_resultados`
  (chave por id, last-write-wins por id distinto) e escrevem artefatos em caminhos
  `{sub_id}__{nome}` disjuntos. Não achei corrida.
- **E1 / guard anti-drift de eventos.** `_tipos_emitidos_em_codigo` é um AST guard real, com
  teste negativo próprio (`test_eventos_schema.py:46`). Ressalva de escopo, não achado: ele
  prova que todo evento emitido está no schema — **não** prova K2 ("toda ação relevante
  produz evento"), que continua sendo julgamento humano.

---

## Reprodução

```bash
cd motor
.venv/bin/python3 -m pytest -q tests/test_auditoria_anthropic_kernel_spec.py
# esperado hoje: 6 failed
```
