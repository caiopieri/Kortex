# Runbook — experimento RAG

Objetivo: medir se um dataset gate-verificado melhora a taxa de aprovação do especialista sem treinar modelo.

Do diretório `motor/`:

```bash
python3 scripts/experimento_rag.py \
  --spec exemplos/rag-rust-ownership.json \
  --fonte-rag <caminho-do-dataset-jsonl> \
  --repeticoes 3
```

Opcional: `--modelos exemplos/modelos-free-escalada.json` ou `--registro exemplos/registro-modelos`.

O script roda a mesma spec em duas condições: `SEM RAG` remove `fonte_rag`; `COM RAG` substitui o
placeholder por `--fonte-rag`. Métrica de sucesso: `COM RAG >= SEM RAG` em taxa de aprovação.

Se não houver lift, confira nos logs o evento `rag.consultado`: `recuperados` precisa ser maior que zero
e os `ids` devem fazer sentido para a tarefa.
