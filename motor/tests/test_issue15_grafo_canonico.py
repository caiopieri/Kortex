"""Contrato causal da issue #15: as superfícies compartilham a topologia."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from motor_painel.painel import dados_painel, grafo_do_log


def _eventos() -> list[dict]:
    return [
        {"seq": 1, "t": 0.0, "evento": "run.perfil", "perfil": "certificado"},
        {
            "seq": 2,
            "t": 0.1,
            "evento": "grafo_dep.iniciado",
            "subagentes": ["A", "B", "C"],
        },
        {"seq": 3, "t": 0.2, "evento": "onda.iniciada", "ids": ["A"]},
        {"seq": 4, "t": 0.3, "evento": "onda.iniciada", "ids": ["B", "C"]},
        {"seq": 5, "t": 0.4, "evento": "aresta.fluxo", "de": "A", "para": "B"},
        {"seq": 6, "t": 0.5, "evento": "aresta.fluxo", "de": "A", "para": "C"},
        {"seq": 7, "t": 0.6, "evento": "tarefa.concluida", "missao": "issue15"},
    ]


def test_dados_expoe_grafo_canonico_por_run(tmp_path: Path) -> None:
    eventos = _eventos()
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(json.dumps(ev) for ev in eventos) + "\n", encoding="utf-8")

    dados = dados_painel(log)
    assert len(dados["runs"]) == 1
    run = dados["runs"][0]
    assert [(a["de"], a["para"]) for a in run["arestas"]] == [
        ("motor", "A"),
        ("motor", "B"),
        ("motor", "C"),
        ("A", "B"),
        ("A", "C"),
    ]
    assert {no["id"] for no in run["nos"]} == {"motor", "A", "B", "C"}


def test_canvas_consumes_o_mesmo_grafo_do_endpoint(tmp_path: Path) -> None:
    eventos = _eventos()
    nos, arestas = grafo_do_log(eventos)
    payload = {"eventos": eventos, "nos": nos, "arestas": arestas}
    script = """
import fs from 'node:fs';
import { projetarRun } from './motor/motor_painel/app/src/canvas/ledger/projetar.js';
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const projetado = projetarRun({ ...payload, fonte: 'cli', id: 'cli#1' });
const topologia = {
  nos: projetado.nos.map((no) => no.id),
  arestas: projetado.arestas,
};
process.stdout.write(JSON.stringify(topologia));
"""
    resultado = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        cwd=Path(__file__).parents[1].parent,
    )
    topologia = json.loads(resultado.stdout)
    assert topologia["nos"] == [no["id"] for no in nos]
    assert topologia["arestas"] == arestas
