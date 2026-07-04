# Item 3B - Frente B - lift-recuperacao v3

Data do run: 2026-07-04

Modelo/provedor sob teste: `codex/gpt-5.4-mini` via provedor `codex`.

## Correcao de isolamento

O primeiro run da Frente B foi interrompido e descartado: rodar `codex exec` dentro do repo contaminava o braco SEM RAG, porque `ClienteCodex` e agentico e usa sandbox `read-only`, portanto o executor podia ler arquivos locais. Isso fez o SEM RAG passar 5/5 antes do isolamento.

Runs validos abaixo foram executados em cwd temporario fora do repo:

- SEM RAG: cwd temporario sem corpus local.
- RAG irrelevante: cwd temporario contendo apenas `rag-controle-negativo-sem-fatos.jsonl`.
- RAG relevante: cwd temporario contendo apenas copia de `rag-docs-metafabrica.jsonl`.

## Fatos usados

| fato | presenca no corpus relevante | ausencia no controle negativo | ausencia do prompt visivel |
|---|---|---|---|
| `auto_esgotar` | `docs/LEIA-PRIMEIRO.md#14` | ausente | ausente |
| `aresta.fluxo` | `docs/ROADMAP.md#14` | ausente | ausente |
| `custo.tick` | `docs/ROADMAP.md#14` | ausente | ausente |
| `sem_secrets_no_diff` | `dev-harness/docs/motor-entrega-profissional.md#16` | ausente | ausente |
| `teste_permissao_cross_tenant` | `dev-harness/docs/motor-entrega-profissional.md#16` | ausente | ausente |

Comandos de prova:

```bash
rg -n "<fato>" exemplos/rag-docs-metafabrica.jsonl
rg -n "<fato>" exemplos/rag-controle-negativo-sem-fatos.jsonl || true
python3 - <<'PY'
import json
from pathlib import Path
spec=json.loads(Path('exemplos/lift-v3-fatos.json').read_text())
sub=spec['subagentes'][0]
visible={'missao': spec['missao'], 'objetivo': sub['objetivo'], 'entradas': sub['entradas'], 'resultado_esperado': sub['resultado_esperado'], 'rubrica': sub['rubrica']}
text=json.dumps(visible, ensure_ascii=False)
for token in ['auto_esgotar','aresta.fluxo','custo.tick','sem_secrets_no_diff','teste_permissao_cross_tenant']:
    print(token, 'PRESENTE' if token in text else 'ausente')
PY
```

## Resultado por braco

| braco | aprovadas | criterio |
|---|---:|---|
| SEM RAG | 1/5 | passa: baseline <= 1/5 |
| RAG irrelevante sem fatos | 0/5 | passa: controle <= 1/5 |
| RAG relevante | 5/5 | passa: recuperacao >= 4/5 |

Veredito contra criterio pre-registrado: **lift de recuperacao provado nesta configuracao isolada**.

## Presenca por repeticao

| braco | rep | aprovado | presentes | faltantes |
|---|---:|---|---|---|
| SEM RAG | 1 | nao | - | `auto_esgotar`, `aresta.fluxo`, `custo.tick`, `sem_secrets_no_diff`, `teste_permissao_cross_tenant` |
| SEM RAG | 2 | sim | `aresta.fluxo`, `custo.tick`, `sem_secrets_no_diff`, `teste_permissao_cross_tenant` | `auto_esgotar` |
| SEM RAG | 3 | nao | `aresta.fluxo`, `custo.tick` | `auto_esgotar`, `sem_secrets_no_diff`, `teste_permissao_cross_tenant` |
| SEM RAG | 4 | nao | - | `auto_esgotar`, `aresta.fluxo`, `custo.tick`, `sem_secrets_no_diff`, `teste_permissao_cross_tenant` |
| SEM RAG | 5 | nao | `auto_esgotar`, `aresta.fluxo`, `custo.tick` | `sem_secrets_no_diff`, `teste_permissao_cross_tenant` |
| RAG irrelevante | 1 | nao | - | todos |
| RAG irrelevante | 2 | nao | - | todos |
| RAG irrelevante | 3 | nao | - | todos |
| RAG irrelevante | 4 | nao | - | todos |
| RAG irrelevante | 5 | nao | - | todos |
| RAG relevante | 1 | sim | todos | - |
| RAG relevante | 2 | sim | todos | - |
| RAG relevante | 3 | sim | todos | - |
| RAG relevante | 4 | sim | `aresta.fluxo`, `custo.tick`, `sem_secrets_no_diff`, `teste_permissao_cross_tenant` | `auto_esgotar` |
| RAG relevante | 5 | sim | `aresta.fluxo`, `custo.tick`, `sem_secrets_no_diff`, `teste_permissao_cross_tenant` | `auto_esgotar` |

## Observacoes

- `auto_esgotar` foi o fato mais fraco no relevante: apareceu em 3/5, mas o validador `min: 4` tolerou essa falha de recuperacao.
- `aresta.fluxo` e `custo.tick` ainda aparecem ocasionalmente no SEM RAG isolado, provavelmente por padrao de nomenclatura de eventos. O criterio pre-registrado aceita baseline 1/5 por aprovacao, mas a presenca por fato mostra que esses dois tokens sao menos fortes que os marcadores de evidencia.
- O resultado prova recuperacao de substring sob isolamento de cwd. Nao prova sintese nem uso combinado dos fatos.
