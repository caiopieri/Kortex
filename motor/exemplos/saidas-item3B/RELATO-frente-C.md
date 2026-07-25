# Item 3B - Frente C - lift-sintese

Data do run: 2026-07-04

Modelo/provedor sob teste: `codex/gpt-5.4-mini` via provedor `codex`.

## Mudanca na spec

`exemplos/lift-derivado.json` foi alterado para remover todos os `pattern` do schema `schema_json`.
O schema agora mede apenas formato: `required`, `type`, `minItems`, `maxItems` e `minLength`.

## Execucao

Os dois bracos foram executados em cwd temporario fora do repo para evitar que `codex exec` lesse o corpus local fora do RAG.

SEM RAG:

```text
SEM RAG: 3/3 aprovadas (100%)
SEM RAG contem: sem validador contem
SEM RAG schema_json: 3/3 aprovadas (100%)
rodada 1: SEM RAG aprovado=True motivo=ok | contem=None | schema_json=True
rodada 2: SEM RAG aprovado=True motivo=ok | contem=None | schema_json=True
rodada 3: SEM RAG aprovado=True motivo=ok | contem=None | schema_json=True
```

COM RAG:

```text
COM RAG: 3/3 aprovadas (100%)
COM RAG contem: sem validador contem
COM RAG schema_json: 3/3 aprovadas (100%)
rodada 1: COM RAG aprovado=True motivo=ok | contem=None | schema_json=True
rodada 2: COM RAG aprovado=True motivo=ok | contem=None | schema_json=True
rodada 3: COM RAG aprovado=True motivo=ok | contem=None | schema_json=True
```

## Respostas cruas do executor

| braco | repeticao | arquivo |
|---|---:|---|
| SEM RAG | 1 | `exemplos/saidas-item3B/frente-C-saidas/sem-rag-01-analista-derivacao.txt` |
| SEM RAG | 2 | `exemplos/saidas-item3B/frente-C-saidas/sem-rag-02-analista-derivacao.txt` |
| SEM RAG | 3 | `exemplos/saidas-item3B/frente-C-saidas/sem-rag-03-analista-derivacao.txt` |
| COM RAG | 1 | `exemplos/saidas-item3B/frente-C-saidas/com-rag-01-analista-derivacao.txt` |
| COM RAG | 2 | `exemplos/saidas-item3B/frente-C-saidas/com-rag-02-analista-derivacao.txt` |
| COM RAG | 3 | `exemplos/saidas-item3B/frente-C-saidas/com-rag-03-analista-derivacao.txt` |

## Leitura

Sem veredito automatico de lift/não-lift nesta frente. O `schema_json` sem regex confirmou apenas que todos os outputs respeitaram o formato minimo. O julgamento semantico das respostas cruas fica para o Arquiteto.
