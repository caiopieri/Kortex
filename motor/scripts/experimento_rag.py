#!/usr/bin/env python3
"""Compara uma WorkflowSpec com e sem fonte RAG."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.__main__ import construir_cliente
from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.politica import PoliticaGates
from motor.spec import WorkflowSpec


def carregar_spec(path):
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    WorkflowSpec.model_validate(spec)
    return spec


def preparar_spec(spec, fonte_rag, com_rag):
    preparada = copy.deepcopy(spec)
    subs = preparada.get("subagentes", [])
    if not com_rag:
        for sub in subs:
            sub.pop("fonte_rag", None)
        return preparada

    alvos = [s for s in subs if s.get("tipo", "modelo") == "modelo" and "fonte_rag" in s]
    if not alvos:
        raise ValueError("a spec precisa declarar fonte_rag em pelo menos um subagente modelo")
    for sub in alvos:
        sub["fonte_rag"] = fonte_rag
    return preparada


def _resumir(resultado):
    if "__interrupt__" in resultado:
        gate = resultado["__interrupt__"][0].value
        return {"aprovado": False, "motivo": f"interrompido no gate {gate.get('portao')}",
                "subagentes": [], "cobertura": {"aprovado": False, "lacunas": gate.get("lacunas", [])}}

    subs = [{
        "id": r.get("id"),
        "aprovado": bool(r.get("aprovado")),
        "motivo": r.get("motivo", "ok" if r.get("aprovado") else "sem motivo"),
    } for r in resultado.get("resultados", [])]
    cobertura = resultado.get("avaliacao", {})
    aprovado = bool(subs) and all(s["aprovado"] for s in subs) and bool(cobertura.get("aprovado"))
    motivo = "ok" if aprovado else "; ".join(str(l) for l in cobertura.get("lacunas", [])) or "reprovado"
    return {"aprovado": aprovado, "motivo": motivo, "subagentes": subs,
            "cobertura": {"aprovado": bool(cobertura.get("aprovado")),
                          "lacunas": cobertura.get("lacunas", [])}}


def executar_rodada(spec, cliente, log_path, thread_id, workspace_base):
    log = LogEventos(log_path)
    try:
        grafo = construir_grafo(
            cliente,
            log,
            checkpointer=InMemorySaver(),
            politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "prosseguir"}),
            workspace_base=workspace_base,
        )
        return _resumir(grafo.invoke({"spec": spec}, {"configurable": {"thread_id": thread_id}}))
    finally:
        log.fechar()


def _rodar_condicao(nome, spec, repeticoes, cliente_factory, workspace):
    rodadas = [
        executar_rodada(
            spec,
            cliente_factory(),
            workspace / f"{nome}-{i}.jsonl",
            f"experimento-rag-{nome}-{i}",
            workspace / "runs",
        )
        for i in range(1, repeticoes + 1)
    ]
    aprovadas = sum(1 for r in rodadas if r["aprovado"])
    return {"nome": nome, "aprovadas": aprovadas, "repeticoes": repeticoes,
            "taxa_aprovacao": aprovadas / repeticoes, "rodadas": rodadas}


def rodar_experimento(spec, *, fonte_rag, repeticoes, cliente_factory, workspace_base):
    if repeticoes < 1:
        raise ValueError("--repeticoes precisa ser >= 1")
    workspace = Path(workspace_base)
    workspace.mkdir(parents=True, exist_ok=True)
    return {
        "sem_rag": _rodar_condicao(
            "sem-rag", preparar_spec(spec, fonte_rag, False), repeticoes, cliente_factory, workspace
        ),
        "com_rag": _rodar_condicao(
            "com-rag", preparar_spec(spec, fonte_rag, True), repeticoes, cliente_factory, workspace
        ),
        "workspace": str(workspace),
    }


def formatar_relatorio(resultado):
    def linha(chave, rotulo):
        item = resultado[chave]
        return f"{rotulo}: {item['aprovadas']}/{item['repeticoes']} aprovadas ({item['taxa_aprovacao'] * 100:.0f}%)"

    linhas = [linha("sem_rag", "SEM RAG"), linha("com_rag", "COM RAG"), f"logs: {resultado['workspace']}"]
    for i, (sem, com) in enumerate(zip(resultado["sem_rag"]["rodadas"], resultado["com_rag"]["rodadas"]), 1):
        linhas.append(
            f"rodada {i}: SEM RAG aprovado={sem['aprovado']} motivo={sem['motivo']} | "
            f"COM RAG aprovado={com['aprovado']} motivo={com['motivo']}"
        )
    return "\n".join(linhas)


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Compara aprovacao de uma spec com e sem RAG.")
    p.add_argument("--spec", required=True)
    p.add_argument("--fonte-rag", required=True)
    p.add_argument("--repeticoes", type=int, default=3)
    p.add_argument("--modelos")
    p.add_argument("--registro")
    p.add_argument("--workspace")
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv or sys.argv[1:])
    cfg = json.loads(Path(args.modelos).read_text(encoding="utf-8")) if args.modelos else None
    workspace = args.workspace or tempfile.mkdtemp(prefix="experimento-rag-")

    resultado = rodar_experimento(
        carregar_spec(args.spec),
        fonte_rag=args.fonte_rag,
        repeticoes=args.repeticoes,
        cliente_factory=lambda: construir_cliente(cfg, args.registro),
        workspace_base=workspace,
    )
    print(formatar_relatorio(resultado))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
