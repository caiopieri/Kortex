# Motor v0.5 — Meta-fábrica

Grafo LangGraph **fixo** que interpreta uma **WorkflowSpec dinâmica**.
Padrão v0: fan-out-and-synthesize com verificação adversarial por subagente,
avaliador global de cobertura e gate do fundador (`interrupt()`).

```bash
pip install -e ".[dev]"
pytest -q                                      # 12 testes, sem rede (ClienteStub)
python -m motor --spec exemplos/missao-pesquisa.json   # requer `claude` CLI
python -m motor "pesquise oportunidades de aumento de receita"
```

Fabricação pendente: ver `HANDOFF.md`. Visão e kernel: vault Obsidian (`2. Pessoal/Meta-fábrica*.md`).
