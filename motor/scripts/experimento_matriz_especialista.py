#!/usr/bin/env python3
"""Matriz 2x2: modelo pequeno/generalista x RAG on/off."""
from __future__ import annotations

import argparse
import os
import json
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REPO = Path(__file__).parent.parent
PROJECT_ROOT = REPO.parent
sys.path.insert(0, str(REPO))

from motor.__main__ import construir_cliente
from scripts.experimento_especialista import carregar_json, carregar_spec, executar, preparar_spec, resumir


def _factory_modelos(cfg: dict[str, Any]):
    return lambda: construir_cliente(cfg, None)


def _assert_cwd_fora_repo(cwd: Path) -> Path:
    resolvido = cwd.resolve()
    repo = PROJECT_ROOT.resolve()
    if resolvido == repo or resolvido.is_relative_to(repo):
        raise ValueError(f"cwd isolado esta dentro do repo: {resolvido}")
    return resolvido


@contextmanager
def _chdir(path: Path):
    anterior = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(anterior)


def _preparar_cwd_celula(nome: str, fonte_rag: str | None) -> tuple[Path, str | None, list[str]]:
    cwd = _assert_cwd_fora_repo(Path(tempfile.mkdtemp(prefix=f"item3B-{nome}-")))
    fonte_para_spec = None
    if fonte_rag is not None:
        destino = cwd / "fonte.jsonl"
        shutil.copyfile(Path(fonte_rag).resolve(), destino)
        fonte_para_spec = destino.name
    return cwd, fonte_para_spec, sorted(item.name for item in cwd.iterdir())


def rodar_matriz(
    spec: dict[str, Any],
    *,
    alvo: str,
    fonte_rag: str,
    repeticoes: int,
    pequeno_modelos: dict[str, Any],
    generalista_modelos: dict[str, Any],
    workspace_base: str | Path,
    precos: dict[str, Any] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_base).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    modelos = [
        ("pequeno", pequeno_modelos),
        ("generalista", generalista_modelos),
    ]
    rags = [("sem_rag", None), ("com_rag", fonte_rag)]
    resultado: dict[str, Any] = {"workspace": str(workspace), "celulas": {}, "isolamento": {}}
    for modelo_nome, cfg in modelos:
        for rag_nome, fonte in rags:
            nome = f"{modelo_nome}_{rag_nome}"
            cwd, fonte_para_spec, conteudo_cwd = _preparar_cwd_celula(nome, fonte)
            spec_celula = preparar_spec(spec, alvo, fonte_para_spec)
            logs = [workspace / f"{nome}-{i}.jsonl" for i in range(1, repeticoes + 1)]
            factory = _factory_modelos(cfg)
            resultado["isolamento"][nome] = {"cwd": str(cwd), "ls": conteudo_cwd}
            with _chdir(cwd):
                rodadas = [
                    executar(
                        spec_celula,
                        factory,
                        logs[i - 1],
                        workspace / "runs",
                    )
                    for i in range(1, repeticoes + 1)
                ]
            resultado["celulas"][nome] = resumir(nome, rodadas, logs, precos)
    return resultado


def formatar_relatorio(resultado: dict[str, Any]) -> str:
    linhas = [
        "| celula | aprovacao deterministica | $ estimado/run | latencia p50 | latencia p90 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for chave in ["pequeno_sem_rag", "pequeno_com_rag", "generalista_sem_rag", "generalista_com_rag"]:
        item = resultado["celulas"][chave]
        custo = item["custo_usd_por_run"]
        linhas.append(
            f"| {chave} | {item['aprovadas']}/{item['repeticoes']} ({item['taxa_aprovacao'] * 100:.0f}%) | "
            f"{'' if custo is None else f'{custo:.8f}'} | {item['latencia_p50_s']:.3f}s | "
            f"{item['latencia_p90_s']:.3f}s |"
        )
    linhas += ["", f"logs: {resultado['workspace']}"]
    if resultado.get("isolamento"):
        linhas += ["", "| celula | cwd | ls |", "| --- | --- | --- |"]
        for chave in ["pequeno_sem_rag", "pequeno_com_rag", "generalista_sem_rag", "generalista_com_rag"]:
            info = resultado["isolamento"][chave]
            linhas.append(f"| {chave} | {info['cwd']} | {', '.join(info['ls']) or '(vazio)'} |")
    for chave in ["pequeno_sem_rag", "pequeno_com_rag", "generalista_sem_rag", "generalista_com_rag"]:
        for i, rodada in enumerate(resultado["celulas"][chave]["rodadas"], 1):
            vals = ",".join(f"{v['kind']}={v['aprovado']}" for v in rodada["validadores"])
            linhas.append(
                f"{chave} rodada {i}: aprovado={rodada['aprovado']} "
                f"latencia={rodada['latencia_s']:.3f}s validadores={vals}"
            )
    return "\n".join(linhas)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Matriz 2x2 modelo x RAG.")
    p.add_argument("--spec", required=True)
    p.add_argument("--alvo", required=True)
    p.add_argument("--fonte-rag", required=True)
    p.add_argument("--repeticoes", type=int, default=5)
    p.add_argument("--pequeno-modelos", required=True)
    p.add_argument("--generalista-modelos", required=True)
    p.add_argument("--precos")
    p.add_argument("--workspace")
    p.add_argument("--saida-json")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)

    resultado = rodar_matriz(
        carregar_spec(args.spec),
        alvo=args.alvo,
        fonte_rag=args.fonte_rag,
        repeticoes=args.repeticoes,
        pequeno_modelos=carregar_json(args.pequeno_modelos) or {},
        generalista_modelos=carregar_json(args.generalista_modelos) or {},
        workspace_base=args.workspace or tempfile.mkdtemp(prefix="experimento-matriz-"),
        precos=carregar_json(args.precos),
    )
    if args.saida_json:
        Path(args.saida_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.saida_json).write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(formatar_relatorio(resultado))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
