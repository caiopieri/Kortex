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


class ClienteDumpPrompts:
    """Delegador que salva prompts crus antes de chamar o cliente real."""

    def __init__(self, base, destino):
        self.base = base
        self.destino = Path(destino)
        self.contadores = {}
        self.destino.mkdir(parents=True, exist_ok=True)

    def __getattr__(self, nome):
        return getattr(self.base, nome)

    def chamar(self, papel, prompt, **kwargs):
        indice = self._proximo_indice(papel)
        self.contadores[papel] = indice
        nome = f"{_slug(papel)}-{indice:02d}.txt"
        (self.destino / nome).write_text(prompt, encoding="utf-8")
        return self.base.chamar(papel, prompt, **kwargs)

    def _proximo_indice(self, papel):
        indice = self.contadores.get(papel, 0) + 1
        while (self.destino / f"{_slug(papel)}-{indice:02d}.txt").exists():
            indice += 1
        return indice


class ClienteMetricaDeterministica:
    """Delegador que mede o executor + validadores sem depender de juiz/sintese LLM."""

    def __init__(self, base):
        self.base = base

    def __getattr__(self, nome):
        return getattr(self.base, nome)

    def chamar(self, papel, prompt, **kwargs):
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "neutro para medir validador deterministico"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        return self.base.chamar(papel, prompt, **kwargs)


def _slug(valor):
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in str(valor)).strip("-") or "papel"


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


def _extrair_validador(resultado_subagente):
    try:
        saida = json.loads(resultado_subagente.get("saida") or "{}")
    except json.JSONDecodeError:
        saida = {}
    if not isinstance(saida, dict) or "kind" not in saida:
        return None
    return {
        "id": resultado_subagente.get("id"),
        "alvo": saida.get("alvo") or resultado_subagente.get("alvo"),
        "kind": saida.get("kind"),
        "aprovado": bool(resultado_subagente.get("aprovado")),
        "motivo": resultado_subagente.get("motivo", ""),
        "evidencia": saida.get("evidencia", {}),
    }


def _resumir(resultado):
    if "__interrupt__" in resultado:
        gate = resultado["__interrupt__"][0].value
        return {"aprovado": False, "motivo": f"interrompido no gate {gate.get('portao')}",
                "subagentes": [], "validadores": [],
                "cobertura": {"aprovado": False, "lacunas": gate.get("lacunas", [])}}

    subs = [{
        "id": r.get("id"),
        "aprovado": bool(r.get("aprovado")),
        "motivo": r.get("motivo", "ok" if r.get("aprovado") else "sem motivo"),
    } for r in resultado.get("resultados", [])]
    validadores = [
        validador
        for r in resultado.get("resultados", [])
        if (validador := _extrair_validador(r)) is not None
    ]
    cobertura = resultado.get("avaliacao", {})
    aprovado = bool(subs) and all(s["aprovado"] for s in subs) and bool(cobertura.get("aprovado"))
    motivo = "ok" if aprovado else "; ".join(str(l) for l in cobertura.get("lacunas", [])) or "reprovado"
    return {"aprovado": aprovado, "motivo": motivo, "subagentes": subs, "validadores": validadores,
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
    validadores_por_kind = _resumir_validadores_por_kind(rodadas)
    return {"nome": nome, "aprovadas": aprovadas, "repeticoes": repeticoes,
            "taxa_aprovacao": aprovadas / repeticoes,
            "validadores": validadores_por_kind,
            "contem": validadores_por_kind.get(
                "contem",
                {"aprovadas": 0, "repeticoes": 0, "taxa_aprovacao": None},
            ),
            "rodadas": rodadas}


def _resumir_validadores_por_kind(rodadas):
    kinds = sorted({
        v.get("kind")
        for rodada in rodadas
        for v in rodada.get("validadores", [])
        if v.get("kind")
    })
    resumo = {}
    for kind in kinds:
        rodadas_com_kind = [
            [v for v in rodada.get("validadores", []) if v.get("kind") == kind]
            for rodada in rodadas
        ]
        rodadas_com_kind = [validadores for validadores in rodadas_com_kind if validadores]
        aprovadas = sum(1 for validadores in rodadas_com_kind if all(v["aprovado"] for v in validadores))
        resumo[kind] = {
            "aprovadas": aprovadas,
            "repeticoes": len(rodadas_com_kind),
            "taxa_aprovacao": (aprovadas / len(rodadas_com_kind) if rodadas_com_kind else None),
        }
    return resumo


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

    def linha_validador(chave, rotulo, kind):
        item = resultado[chave]["validadores"].get(kind)
        if item is None and kind == "contem":
            item = resultado[chave].get("contem")
        if item["taxa_aprovacao"] is None:
            return f"{rotulo} {kind}: sem validador {kind}"
        return (
            f"{rotulo} {kind}: {item['aprovadas']}/{item['repeticoes']} aprovadas "
            f"({item['taxa_aprovacao'] * 100:.0f}%)"
        )

    linhas = [
        linha("sem_rag", "SEM RAG"),
        linha("com_rag", "COM RAG"),
    ]
    kinds = sorted(
        set(resultado["sem_rag"].get("validadores", {})) |
        set(resultado["com_rag"].get("validadores", {})) |
        {"contem"}
    )
    for kind in kinds:
        linhas.append(linha_validador("sem_rag", "SEM RAG", kind))
        linhas.append(linha_validador("com_rag", "COM RAG", kind))
    linhas.append(f"logs: {resultado['workspace']}")
    for i, (sem, com) in enumerate(zip(resultado["sem_rag"]["rodadas"], resultado["com_rag"]["rodadas"]), 1):
        status_validadores = []
        for kind in kinds:
            sem_validadores = [v for v in sem.get("validadores", []) if v.get("kind") == kind]
            com_validadores = [v for v in com.get("validadores", []) if v.get("kind") == kind]
            sem_ok = all(v["aprovado"] for v in sem_validadores) if sem_validadores else None
            com_ok = all(v["aprovado"] for v in com_validadores) if com_validadores else None
            status_validadores.append(f"{kind} SEM={sem_ok} COM={com_ok}")
        linhas.append(
            f"rodada {i}: SEM RAG aprovado={sem['aprovado']} motivo={sem['motivo']} | "
            f"COM RAG aprovado={com['aprovado']} motivo={com['motivo']} | "
            f"{' | '.join(status_validadores)}"
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
    p.add_argument(
        "--somente-metrica-deterministica",
        action="store_true",
        help="usa modelo real so nos executores; verifier/evaluator/synthesizer viram respostas neutras",
    )
    p.add_argument(
        "--dump-prompts",
        help="diretorio para salvar o prompt cru de cada chamada ao cliente",
    )
    return p.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv or sys.argv[1:])
    cfg = json.loads(Path(args.modelos).read_text(encoding="utf-8")) if args.modelos else None
    workspace = args.workspace or tempfile.mkdtemp(prefix="experimento-rag-")

    def cliente_factory():
        cliente = construir_cliente(cfg, args.registro)
        if args.dump_prompts:
            cliente = ClienteDumpPrompts(cliente, args.dump_prompts)
        if args.somente_metrica_deterministica:
            return ClienteMetricaDeterministica(cliente)
        return cliente

    resultado = rodar_experimento(
        carregar_spec(args.spec),
        fonte_rag=args.fonte_rag,
        repeticoes=args.repeticoes,
        cliente_factory=cliente_factory,
        workspace_base=workspace,
    )
    print(formatar_relatorio(resultado))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
