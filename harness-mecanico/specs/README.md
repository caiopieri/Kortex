# specs/ — WorkflowSpecs por degrau

> Cada arquivo é uma **WorkflowSpec** (schema v0.1 do motor, `motor/spec.py`) que descreve um pipeline mecânico como dado — `padrao: "grafo_dependencias"`, cadeia de subagentes (`modelo` e `ferramenta`) ligados por `depende_de` + `ref_artefato`. A dinâmica vive aqui, não em código.

## Próximo passo concreto e falsificável: `M2-bracket.json`

A 1ª spec real — um **bracket sob carga** — deve **validar contra o schema do motor sem rodar física**, provando a premissa "M2 roda hoje". Cadeia mínima:

```
requisitos(modelo) → analitico(modelo/ferramenta) → cad(ferramenta: cadquery-runner)
   → malha(ferramenta: gmsh-mesher) → fea(ferramenta: calculix-solver)
   → reconciliacao(ferramenta: reconciliation-checker) → dfm(ferramenta: dfm-linter)
   → pacote(modelo: desenho+BOM)
```

Cada seta a jusante recebe o artefato anterior via `entradas` com `ref_artefato`:
```json
"entradas": { "geometria": { "ref_artefato": { "de": "cad", "nome": "part.step" } } }
```

Pontos de atenção ao escrever (verificados no schema):
- subagente `tipo: "modelo"` exige `papel` **e** `rubrica` não-vazia (spec.py L80–85).
- subagente `tipo: "ferramenta"` exige `ferramenta` (nome lógico que existe em `ferramentas/`).
- `ref_artefato.de` precisa estar em `depende_de` e apontar artefato **declarado** pela origem (spec.py L148–165).
- `criterios_cobertura` da missão devem ser checáveis (ex.: "FS por modo de falha calculado", "rating de manufaturabilidade presente", "reconciliação dentro da tolerância").

## Convenção de validação (antes de rodar física)

```bash
cd ../motor
python3 -c "import json; from motor.spec import WorkflowSpec; \
WorkflowSpec.model_validate(json.load(open('../harness-mecanico/specs/M2-bracket.json'))); \
print('spec M2 válida')"
```

Só depois de a spec validar é que se constroem/encaixam as `ferramentas/` reais e se roda ponta-a-ponta. **Validar o esqueleto antes de gastar solver** é a aplicação da cultura "spec travada → produz → verifica" ao caso mecânico.

## Degraus seguintes
`M3-*` (fadiga/térmica/modal/CFD — adiciona solvers e checadores), `M4-*` (submontagem + cadeia de tolerâncias + clash), `M5-*` (máquina). Cada um endurece sob a [[../01-CONSTITUICAO-MECANICA|constituição]], não tudo de uma vez.
