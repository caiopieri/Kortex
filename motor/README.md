# Motor v0.5 — Meta-fábrica

Grafo LangGraph **fixo** que interpreta uma **WorkflowSpec dinâmica**.
Padrão v0: fan-out-and-synthesize com verificação adversarial por subagente,
avaliador global de cobertura e gate do fundador (`interrupt()`).

```bash
python -m pip install -e ".[dev]"
python -m pytest -q                            # suíte sem rede (ClienteStub)
python -m motor --modelos /caminho/modelos-orcados.json --spec exemplos/missao-pesquisa.json  # fail-closed
python -m motor --modelos /caminho/modelos-orcados.json "pesquise oportunidades"             # fail-closed
```

Esses comandos exercitam a composição, mas a rota única e o teto padrão ainda não completam uma
missão real. O arquivo deve declarar `orcamento_openai`, apontar a credencial por variável de ambiente
e carregar snapshot FX fresco. Os antigos `exemplos/modelos-*.json` não são configuração de produção.

O entrypoint do LangGraph Studio está temporariamente **indisponível**: `make_graph()` falha fechado
porque o Studio não fornece hoje identidade de run, ledger de orçamento e sink monetário duráveis.
Não há promessa de startup nem execução funcional até a composição custeada ser integrada.

Dependências opcionais do Studio:

```bash
pip install -e ".[dev,studio]"
langgraph dev
```

Se mexer em dependências, pare o `langgraph dev` antes. O hot reload observa
mudanças em `.venv` e pode reiniciar enquanto o pip ainda está escrevendo arquivos.

Arquitetura do sistema: **`../docs/ARCHITECTURE.md`**. Norte do motor:
`docs/EVOLUCAO.md`. Fronteira MCP/orquestrador: `docs/ARQUITETURA-MCP.md`. Invariantes:
`docs/INVARIANTES.md`. Mapa operacional: `../docs/ROADMAP.md`.
