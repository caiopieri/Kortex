# Runbook — experimento RAG

Objetivo: medir se um dataset gate-verificado melhora a taxa de aprovação sem treinar o
modelo. O protocolo normativo está em
`../specs/003-experimentos-reprodutiveis/spec.md`.

Do diretório `motor/`:

```bash
python3 scripts/docs_para_rag.py

python3 scripts/experimento_rag.py \
  --spec exemplos/lift-derivado.json \
  --fonte-rag exemplos/rag-docs-metafabrica.jsonl \
  --repeticoes 5
```

O primeiro comando gera localmente o dataset ignorado pelo Git a partir da documentação
pública. Para outro corpus, passe `--fonte` e `--saida` explicitamente.

Opcional: `--modelos exemplos/modelos-free-escalada.json` ou `--registro exemplos/registro-modelos`.

O script roda a mesma spec em duas condições: `SEM RAG` remove `fonte_rag`; `COM RAG`
substitui o placeholder por `--fonte-rag`. Para uma conclusão causal, execute também um braço
com contexto irrelevante, mantenha modelo e parâmetros fixos e registre o critério de sucesso
antes da coleta. `COM RAG >= SEM RAG` sozinho não demonstra lift.

Se não houver lift, confira nos logs o evento `rag.consultado`: `recuperados` precisa ser maior que zero
e os `ids` devem fazer sentido para a tarefa.

Rode os braços em diretórios temporários distintos, fora do repositório, e retenha as saídas
cruas. Um fato já presente no checkout invalida o experimento.
