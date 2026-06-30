# Motor v0.5 — Meta-fábrica

Grafo LangGraph **fixo** que interpreta uma **WorkflowSpec dinâmica**.
Padrão v0: fan-out-and-synthesize com verificação adversarial por subagente,
avaliador global de cobertura e gate do fundador (`interrupt()`).

```bash
pip install -e ".[dev]"
pytest -q                                      # ~244 testes, sem rede (ClienteStub)
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

Visão do sistema inteiro: **`../LEIA-PRIMEIRO.md`** (comece por aí). Norte do motor:
`EVOLUCAO-motor-pos-v05.md`. Fronteira MCP/orquestrador: `ARQUITETURA-MCP-e-orquestrador.md`. Mapa
operacional: `../ROADMAP-META-FABRICA.md`. Kernel canônico de longo prazo: vault Obsidian
(`2. Pessoal/Meta-fábrica*.md`). Handoffs de trabalho: `HANDOFF-CODEX-*.md`.
