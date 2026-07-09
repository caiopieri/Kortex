#!/usr/bin/env python3
"""A/B: especialista barato+RAG vs generalista topo na mesma tarefa."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
import time
from math import ceil
from pathlib import Path
from typing import Any, Callable, cast

REPO = Path(__file__).parent.parent
sys.path.insert(0, str(REPO))

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.__main__ import construir_cliente  # noqa: E402
from motor.curador import analisar  # noqa: E402
from motor.eventos import LogEventos  # noqa: E402
from motor.grafo import construir_grafo  # noqa: E402
from motor.modelos import ClienteModelo  # noqa: E402
from motor.politica import PoliticaGates  # noqa: E402
from motor.spec import WorkflowSpec  # noqa: E402
from scripts.experimento_rag import ClienteMetricaDeterministica  # noqa: E402


class ClienteUsoEstimado:
    def __init__(self, base: Any, log: LogEventos):
        self.base, self.log = base, log

    def __getattr__(self, nome: str) -> Any:
        return getattr(self.base, nome)

    def descricao_de(self, *args: Any, **kwargs: Any) -> str | None:
        if hasattr(self.base, "descricao_de"):
            return self.base.descricao_de(*args, **kwargs)
        prov, modelo = getattr(self.base, "provedor", None), getattr(self.base, "modelo", None)
        return f"{prov}/{modelo}" if prov and modelo else (str(prov or modelo) if prov or modelo else None)

    def chamar(self, papel: str, prompt: str, **kwargs: Any) -> str | None:
        resposta = self.base.chamar(papel, prompt, **kwargs)
        if resposta is not None:
            desc = self.descricao_de(papel, kwargs.get("tier"), kwargs.get("ferramentas"), kwargs.get("capacidades")) or "desconhecido"
            prov, modelo = ("", desc) if "/" not in desc else desc.split("/", 1)
            entrada, saida = max(1, ceil(len(prompt) / 4)), max(1, ceil(len(resposta) / 4))
            self.log.evento("modelo.uso", papel=papel, provedor=prov, modelo=modelo,
                            prompt_tokens=entrada, completion_tokens=saida,
                            total_tokens=entrada + saida, estimado=True)
        return resposta


def carregar_json(path: str | None) -> dict[str, Any] | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def carregar_spec(path: str | Path) -> dict[str, Any]:
    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    WorkflowSpec.model_validate(spec)
    return spec


def preparar_spec(spec: dict[str, Any], alvo: str, fonte_rag: str | None) -> dict[str, Any]:
    preparada, achou = copy.deepcopy(spec), False
    for sub in preparada.get("subagentes", []):
        if sub.get("id") == alvo:
            achou = True
            sub.pop("fonte_rag", None) if fonte_rag is None else sub.__setitem__("fonte_rag", fonte_rag)
    if not achou:
        raise ValueError(f"alvo nao encontrado: {alvo}")
    WorkflowSpec.model_validate(preparada)
    return preparada


def _validadores(resultado: dict[str, Any]) -> list[dict[str, Any]]:
    saida = []
    for item in resultado.get("resultados", []):
        try:
            dados = json.loads(item.get("saida") or "{}")
        except json.JSONDecodeError:
            continue
        if isinstance(dados, dict) and "kind" in dados:
            saida.append({"kind": dados.get("kind"), "aprovado": bool(item.get("aprovado"))})
    return saida


def executar(spec: dict[str, Any], factory: Callable[[], Any], log_path: Path, workspace: Path) -> dict[str, Any]:
    log, inicio = LogEventos(log_path), time.perf_counter()
    try:
        cliente = cast(ClienteModelo, ClienteMetricaDeterministica(ClienteUsoEstimado(factory(), log)))
        grafo = construir_grafo(cliente, log, checkpointer=InMemorySaver(),
                                politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "prosseguir"}),
                                workspace_base=workspace)
        resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": log_path.stem}})
    finally:
        latencia = round(time.perf_counter() - inicio, 3)
        log.fechar()
    vals = _validadores(resultado)
    return {"aprovado": bool(vals) and all(v["aprovado"] for v in vals),
            "latencia_s": latencia, "validadores": vals, "log": str(log_path)}


def _pct(valores: list[float], pct: float) -> float:
    ordenados = sorted(valores)
    return ordenados[max(0, min(len(ordenados) - 1, ceil(len(ordenados) * pct) - 1))]


def resumir(nome: str, rodadas: list[dict[str, Any]], logs: list[Path], precos: dict[str, Any] | None) -> dict[str, Any]:
    custos = analisar(list(logs), precos=precos, incluir_rascunho=True)["custo"]["por_run"]
    usd = [c["custo_usd"] for c in custos if c.get("custo_usd") is not None]
    lat = [float(r["latencia_s"]) for r in rodadas]
    ok = sum(1 for r in rodadas if r["aprovado"])
    return {"nome": nome, "aprovadas": ok, "repeticoes": len(rodadas), "taxa_aprovacao": ok / len(rodadas),
            "latencia_p50_s": _pct(lat, 0.50), "latencia_p90_s": _pct(lat, 0.90),
            "custo_usd_por_run": round(sum(usd) / len(usd), 8) if usd else None, "rodadas": rodadas}


def rodar_ab(spec: dict[str, Any], *, alvo: str, fonte_rag: str, repeticoes: int,
             barato_factory: Callable[[], Any], topo_factory: Callable[[], Any],
             workspace_base: str | Path, precos: dict[str, Any] | None = None) -> dict[str, Any]:
    workspace = Path(workspace_base)
    workspace.mkdir(parents=True, exist_ok=True)
    bracos = [
        ("barato_rag", preparar_spec(spec, alvo, fonte_rag), barato_factory),
        ("topo_sem_rag", preparar_spec(spec, alvo, None), topo_factory),
    ]
    resultado: dict[str, Any] = {"workspace": str(workspace), "bracos": {}}
    for nome, spec_braco, factory in bracos:
        logs = [workspace / f"{nome}-{i}.jsonl" for i in range(1, repeticoes + 1)]
        rodadas = [executar(spec_braco, factory, logs[i - 1], workspace / "runs") for i in range(1, repeticoes + 1)]
        resultado["bracos"][nome] = resumir(nome, rodadas, logs, precos)
    return resultado


def formatar_relatorio(resultado: dict[str, Any]) -> str:
    linhas = ["| braço | aprovação determinística | $ estimado/run | latência p50 | latência p90 |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for chave in ["barato_rag", "topo_sem_rag"]:
        b, custo = resultado["bracos"][chave], resultado["bracos"][chave]["custo_usd_por_run"]
        linhas.append(f"| {chave} | {b['aprovadas']}/{b['repeticoes']} ({b['taxa_aprovacao'] * 100:.0f}%) | "
                      f"{'' if custo is None else f'{custo:.8f}'} | {b['latencia_p50_s']:.3f}s | {b['latencia_p90_s']:.3f}s |")
    linhas += ["", f"logs: {resultado['workspace']}"]
    for chave in ["barato_rag", "topo_sem_rag"]:
        for i, r in enumerate(resultado["bracos"][chave]["rodadas"], 1):
            vals = ",".join(f"{v['kind']}={v['aprovado']}" for v in r["validadores"])
            linhas.append(f"{chave} rodada {i}: aprovado={r['aprovado']} latencia={r['latencia_s']:.3f}s validadores={vals}")
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="A/B especialista barato+RAG vs topo sem RAG.")
    p.add_argument("--spec", required=True)
    p.add_argument("--fonte-rag", required=True)
    p.add_argument("--alvo", default="transformador-csv-json")
    p.add_argument("--repeticoes", type=int, default=15)
    p.add_argument("--barato-modelos", required=True)
    p.add_argument("--topo-modelos")
    p.add_argument("--precos")
    p.add_argument("--workspace")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)
    resultado = rodar_ab(carregar_spec(args.spec), alvo=args.alvo, fonte_rag=args.fonte_rag,
                         repeticoes=args.repeticoes,
                         barato_factory=lambda: construir_cliente(carregar_json(args.barato_modelos), None),
                         topo_factory=lambda: construir_cliente(carregar_json(args.topo_modelos), None),
                         workspace_base=args.workspace or tempfile.mkdtemp(prefix="experimento-especialista-"),
                         precos=carregar_json(args.precos))
    print(formatar_relatorio(resultado))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
