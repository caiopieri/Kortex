# Motor v0.5 — Meta-fábrica

Grafo LangGraph **fixo** que interpreta uma **WorkflowSpec dinâmica**.
Padrão v0: fan-out-and-synthesize com verificação adversarial por subagente,
avaliador global de cobertura e gate do fundador (`interrupt()`).

```bash
python -m pip install -e ".[dev]"
python -m pytest -q                            # suíte sem rede (ClienteStub)
python -m motor --spec exemplos/missao-pesquisa.json   # requer `claude` CLI
python -m motor "pesquise oportunidades de aumento de receita"
```

LangGraph Studio local, sem Docker:

```bash
pip install -e ".[dev,studio]"
langgraph dev
```

Se mexer em dependências, pare o `langgraph dev` antes. O hot reload observa
mudanças em `.venv` e pode reiniciar enquanto o pip ainda está escrevendo arquivos.

Arquitetura do sistema: **`../docs/ARCHITECTURE.md`**. Norte do motor:
`docs/EVOLUCAO.md`. Fronteira MCP/orquestrador: `docs/ARQUITETURA-MCP.md`. Invariantes:
`docs/INVARIANTES.md`. Mapa operacional: `../docs/ROADMAP.md`.
