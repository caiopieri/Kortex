# ferramentas/ — entidades de ferramenta do Registry

> Cada arquivo `.md` aqui é uma **entidade de ferramenta** que o motor carrega via `ferramentas_de_registro` (registro.py L167–183) e o nó-`ferramenta` resolve em runtime. São os **gates determinísticos** e os **executores** do pipeline mecânico — exit 0/1 (ou JSON via MR-2), nunca julgamento de modelo.

## Formato da entidade (frontmatter)

```markdown
---
tipo: ferramenta
nome: calculix-solver            # nome lógico referenciado pelo subagente (campo `ferramenta`)
comando: "ccx_runner {input_inp} {out_results}"   # placeholders ← entradas/produz
interpreta_saida: json           # exit_code (hoje) | json (após MR-2)
timeout: 3600                    # segundos (requer MR-1; default 300)
produz:
  - nome: results.json
    tipo: fea-result
    de_placeholder: out_results  # o motor injeta o caminho de saída neste placeholder
---
Descrição: o que faz, pré-requisitos de máquina, como interpretar a saída,
e contra qual norma/limite gateia.
```

Regras (do código): `comando` é `shlex.split` + `format_map(entradas)`; executável ausente → `ferramenta.indisponivel` (falha explícita); saída declarada em `produz` que não aparece no disco → reprova. Ver `02-REQUISITOS-AO-MOTOR.md`.

## Ferramentas a construir (mínimo para M2)

| nome | papel no pipeline | interpreta_saida | gateia? |
|---|---|---|---|
| `cadquery-runner` | executa script build123d/CadQuery → STEP + STL | exit_code | não (produz) |
| `gmsh-mesher` | STEP → malha + **gate de qualidade** (jacobiano, aspect ratio) | json | sim (qualidade de malha) |
| `calculix-solver` | malha + cargas → campo de resultado (.frd/results.json) | json | não (produz métricas) |
| `reconciliation-checker` | results.json **+** analytical.json → `|FEA−analítico|/analítico ≤ tol` + convergência + FS por modo | json | **sim (Artigo 2)** |
| `dfm-linter` | geometria + perfil de fornecedor → conformidade + rating de risco | json | **sim (Artigo 5/6)** |
| `mass-props` | sólido → massa, CG, volume, inércia | json | não |
| `clash-detector` | peça + envelope espacial compartilhado → interferência | exit_code | **sim (fronteira inter-harness)** |
| `tolerance-stack` | features + tolerâncias → pior caso + RSS estatístico | json | sim (Artigo 4) |

> M3+ adiciona: `openfoam-runner` (CFD), `fatigue-checker` (S-N / Goodman), `modal-checker` (frequências naturais vs. excitação), `topopt-runner` (SIMP + reconstrução).

## Princípio
A inteligência mecânica **não** está no solver — está em montar o problema (contorno/carga/malha) e em **desconfiar do resultado**. Estas ferramentas são o encanamento determinístico; o julgamento vive nos nós-modelo e nos gates de reconciliação. Uma ferramenta que "sempre passa" é um gate inútil.
