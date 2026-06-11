"""CLI mínima do motor v0.5.

  python -m motor "sua missão aqui"            # planner cria a WorkflowSpec
  python -m motor --spec exemplos/missao.json  # missão dirigida por spec pronta
  python -m motor ... --caixa "<dir>"          # gate via nota no vault + resume durável

Requer `claude` CLI no PATH (Mac do Caio). Gate do fundador: sem `--caixa`, a
decisão é via input() e o checkpointer é em memória (volátil). Com `--caixa
<dir>`, a decisão vai para uma nota na Caixa do fundador (T3) e o estado do
grafo é persistido em `motor.db` na raiz do repo — religar o processo retoma do
gate pendente.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from langgraph.types import Command

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # nome antigo
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from langgraph.checkpoint.sqlite import SqliteSaver

from .caixa import CaixaFundador, rodar_com_caixa
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

    # --caixa <dir>: gate via nota no vault + checkpointer SQLite durável.
    dir_caixa = None
    if "--caixa" in args:
        i = args.index("--caixa")
        dir_caixa = args[i + 1]
        args = args[:i] + args[i + 2:]

    entrada: dict
    if args[0] == "--spec":
        entrada = {"spec": json.loads(Path(args[1]).read_text(encoding="utf-8"))}
    else:
        entrada = {"missao_texto": " ".join(args)}

    raiz = Path(__file__).parent.parent
    log = LogEventos(raiz / "log.jsonl")
    config = {"configurable": {"thread_id": "cli"}}

    if dir_caixa:
        # Persistente: sobrevive a crash. Conexão própria (check_same_thread=False)
        # para não fechar ao sair de um context manager — durabilidade real exige
        # que o arquivo motor.db permaneça consistente entre execuções.
        conn = sqlite3.connect(str(raiz / "motor.db"), check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        checkpointer.setup()
        grafo = construir_grafo(ClienteClaudeCLI(log=log), log, checkpointer=checkpointer)
        caixa = CaixaFundador(dir_caixa, log)
        resultado = rodar_com_caixa(grafo, entrada, config, caixa, log)
        conn.close()
    else:
        # Comportamento default intacto: input() + InMemorySaver (volátil).
        grafo = construir_grafo(ClienteClaudeCLI(log=log), log, checkpointer=InMemorySaver())
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
