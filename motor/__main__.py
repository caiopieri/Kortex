"""CLI mínima do motor v0.5.

  python -m motor "sua missão aqui"            # planner cria a WorkflowSpec
  python -m motor --spec exemplos/missao.json  # missão dirigida por spec pronta

Requer `claude` CLI no PATH (Mac do Caio). Gate do fundador: nesta CLI a decisão
é via input(); a integração com a Caixa do fundador no vault é a tarefa T3 do HANDOFF.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from langgraph.types import Command

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # nome antigo
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from .eventos import LogEventos
from .grafo import construir_grafo
from .modelos import ClienteClaudeCLI


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if not ClienteClaudeCLI.disponivel():
        print("erro: `claude` CLI não encontrado no PATH — rode no Mac do Caio ou use o ClienteStub em testes.")
        return 1

    entrada: dict
    if args[0] == "--spec":
        entrada = {"spec": json.loads(Path(args[1]).read_text(encoding="utf-8"))}
    else:
        entrada = {"missao_texto": " ".join(args)}

    log = LogEventos(Path(__file__).parent.parent / "log.jsonl")
    grafo = construir_grafo(ClienteClaudeCLI(), log, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "cli"}}

    resultado = grafo.invoke(entrada, config)
    while "__interrupt__" in resultado:  # gate do fundador
        pedido = resultado["__interrupt__"][0].value
        print(f"\n[GATE {pedido['portao']}] {pedido['pergunta']}")
        print(f"  lacunas: {pedido.get('lacunas')}\n  opções: {pedido['opcoes']}")
        decisao = input("decisão> ").strip()
        resultado = grafo.invoke(Command(resume=decisao), config)

    print("\n=== RESPOSTA FINAL ===\n")
    print(resultado.get("resposta_final", "(missão abortada)"))
    log.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
