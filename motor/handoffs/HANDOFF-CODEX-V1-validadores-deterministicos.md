# HANDOFF CODEX — V1: nós validadores DETERMINÍSTICOS na WorkflowSpec (o salto anti-alucinação)

## Por quê (EVOLUCAO V1 + biblioteca-de-validadores)
Hoje os gates do grafo são LLM (verifier adversarial, evaluator). A `dev-harness/docs/biblioteca-de-validadores.md`
diz: **determinístico > adversarial > humano** — quando existe uma checagem por algoritmo que prende a
afirmação, ela é o default. Este handoff adiciona à spec um **novo tipo de nó: `validador`** — cuja
"capacidade" é um ALGORITMO (validar schema, checar presença), não `cliente.chamar`. É o grafo híbrido
virando real: agente = peça pensante; validador determinístico = a verdade. É onde estamos à frente do
Paperclip ("Enforced Outcomes" não-feito).

Escopo do V1 (falsificável-cheap-first): **só as 2 famílias mais baratas e PURAS** — `schema_json` e
`contem` — que não executam nada (sem pytest/compile/SAST, que exigem sandbox e vêm depois). Inerte por
default: spec sem nó `validador` = comportamento atual idêntico.

## Base que já existe (não reinventar)
- `motor/spec.py`: `Subagente.tipo: Literal["modelo","ferramenta"]`; já há nó `ferramenta` (produtor).
- `motor/grafo.py`: no nó `subagente`, `if sub.get("tipo")=="ferramenta": return executar_ferramenta(...)`.
- `grafo_dependencias` roda nós em ondas por `depende_de`, passando a saída da dependência em `deps`.
- "reprovado vira lacuna por código" já existe (subagente reprovado → cobertura → reconciliação).
- `eventos_schema.py` com guarda anti-drift (evento novo tem que ser declarado).

## Mudança (motor/spec.py + motor/grafo.py + motor/eventos_schema.py)

### 1. Spec: tipo `validador`
`Subagente.tipo`: `Literal["modelo","ferramenta","validador"]`. Campos p/ o validador:
```python
valida: Optional[str] = Field(default=None, description="id do subagente cuja saída este nó valida (determinístico)")
validador: Optional[dict] = Field(default=None, description="{'kind': 'schema_json'|'contem', 'config': {...}}")
```
Regras de validação (no validador da WorkflowSpec):
- `tipo=="validador"` exige `valida` (alvo) e `validador` com `kind` ∈ {schema_json, contem}.
- um nó validador **depende do alvo**: exigir `valida in depende_de` (ou adicioná-lo automaticamente) —
  ele roda DEPOIS do alvo, lendo a saída dele.
- validador NÃO exige papel/rubrica (não é modelo); não chama LLM.

### 2. Grafo: executar o validador (determinístico)
No nó `subagente`, antes do fluxo de modelo, tratar `tipo=="validador"` (espelhando o branch de
`ferramenta`): ler a saída do alvo (via `deps[valida]` / `concluidos[valida]`), rodar a checagem pura e
produzir um `resultado` `{id, aprovado, motivo, evidencia}`:
- **`schema_json`**: `config={"schema": <JSON Schema>}`. Parseia a saída do alvo como JSON e valida contra
  o schema (use `jsonschema`, que já é dependência transitiva; se não for, validação mínima manual —
  decida e documente). Aprovado sse parseia E casa. `motivo` = erro do validador.
- **`contem`**: `config={"requer": ["<substring/tópico>", ...], "min": N?}`. Aprovado sse a saída do alvo
  contém todos (ou ≥min) os itens exigidos (case-insensitive). Determinístico, sem LLM. `motivo` = o que faltou.
- Emitir evento **`validador.rodou`** `{id, alvo, kind, aprovado, motivo}` (declarar no eventos_schema).
- **Reprovado vira lacuna por código**: o `resultado` do validador com `aprovado=false` entra em
  `resultados` como reprovado → `avaliar_cobertura` já o transforma em lacuna → reconciliação pode
  re-disparar o ALVO (o `valida`) — reusa 100% o mecanismo existente. (Garanta que o `id` reprovado que
  vira lacuna aponte pro alvo certo: ou o validador nomeia o alvo em `nos_a_refazer`-equivalente, ou o
  motivo cita o alvo; o importante é o alvo ser re-disparável.)

### 3. eventos_schema
Declarar `validador.rodou` (categoria `gate` ou nova `validador`; campos id, alvo, kind, aprovado, motivo).

## Restrições (inerte / escopo)
- SÓ `schema_json` e `contem` neste corte. **Nada que execute código** (pytest/compile/SAST = famílias
  futuras, precisam de sandbox — NÃO fazer agora).
- Inerte por default: spec sem `tipo:validador` = suíte atual intacta.
- Não mexer no verifier/evaluator LLM (eles continuam pros critérios que NÃO são determinizáveis). O
  validador é ADITIVO — cobre a afirmação determinizável; o resto segue adversarial.
- stdlib + jsonschema (se já disponível). Sem execução de código do usuário/dataset.

## DoD (todos determinísticos — validador não chama LLM)
1. **schema_json aprova/reprova**: nó validador com schema; alvo produz JSON válido → aprovado; alvo
   produz JSON que viola o schema → reprovado, `validador.rodou` com aprovado=false, e vira lacuna no
   cobertura.
2. **contem aprova/reprova**: `requer` presente na saída do alvo → aprovado; ausente → reprovado + lacuna.
3. **reprovado re-dispara o alvo**: com reconciliação ligada (`--gate cobertura=preencher`/override), um
   validador reprovado leva a re-executar o `valida` (o alvo), não o próprio validador.
4. **inerte**: spec sem nó validador → nenhum `validador.rodou`, suíte atual intacta.
5. Guarda anti-drift verde (evento declarado). Suíte verde (257+); compileall; mypy ok.

## Depois (não agora — famílias que executam)
`pytest`/`compile`/`SAST`/`numérico` exigem sandbox e política de execução — família V1.x, com as mesmas
regras de segurança. E a **catraca do curador**: propor transformar achado adversarial recorrente em
validador determinístico (biblioteca §6) — entra com a fatia 3 do curador.
