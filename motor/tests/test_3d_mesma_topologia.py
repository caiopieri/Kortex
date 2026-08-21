"""O 3D é outro renderizador da MESMA projeção — irmão de `test_issue15_grafo_canonico`.

A issue #15 aconteceu porque duas superfícies liam o mesmo log e chegavam a
grafos diferentes: o defeito era **projetar** duas vezes, não desenhar duas
vezes. A correção fez de `grafo_do_log` a projeção canônica.

O modo 3D do canvas só pode existir sob essa regra: uma projeção, N
renderizadores. Este arquivo trava as duas metades disso.

1. TOPOLOGIA — o que o 3D desenha são exatamente os nós e arestas que o
   `/dados` emitiu para aquela run, os mesmos que o 2D posiciona. Nenhum a
   mais, nenhum a menos.

2. POSIÇÃO — o Z vem da ONDA DECLARADA (`onda.iniciada`), nunca da física.
   Grafo force-directed livre inventa coordenada, e inventar lugar é o que
   tirou o MapaGeral do painel. A física fica confinada a X e Y, que é o mesmo
   arbítrio que o 2D já faz ao empilhar em linha dentro da onda.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from motor_painel.painel import dados_painel, grafo_do_log

RAIZ = Path(__file__).parents[1].parent
LEDGER = "./motor/motor_painel/app/src/canvas/ledger"


def _eventos() -> list[dict]:
    """Duas ondas, para a profundidade ter mais de um valor."""
    return [
        {"seq": 1, "t": 0.0, "evento": "run.perfil", "perfil": "certificado"},
        {"seq": 2, "t": 0.1, "evento": "grafo_dep.iniciado", "subagentes": ["A", "B", "C"]},
        {"seq": 3, "t": 0.2, "evento": "onda.iniciada", "ids": ["A"]},
        {"seq": 4, "t": 0.3, "evento": "onda.iniciada", "ids": ["B", "C"]},
        {"seq": 5, "t": 0.4, "evento": "aresta.fluxo", "de": "A", "para": "B"},
        {"seq": 6, "t": 0.5, "evento": "aresta.fluxo", "de": "A", "para": "C"},
        {"seq": 7, "t": 0.6, "evento": "executor.erro", "executor": "B", "motivo": "modelo não respondeu", "tentativa": 1},
        {"seq": 8, "t": 0.7, "evento": "tarefa.concluida", "missao": "3d"},
    ]


def _no_navegador(script: str, payload: dict) -> dict:
    resultado = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
        cwd=RAIZ,
    )
    return json.loads(resultado.stdout)


def _projetado(eventos: list[dict]) -> dict:
    nos, arestas = grafo_do_log(eventos)
    script = f"""
import fs from 'node:fs';
import {{ projetarRun }} from '{LEDGER}/projetar.js';
import {{ projetar3d }} from '{LEDGER}/layout3d.js';
import {{ posicionarNos }} from '{LEDGER}/layout.js';
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const run = projetarRun({{ ...payload, fonte: 'cli', id: 'cli#1' }});
const trid = projetar3d(run);
process.stdout.write(JSON.stringify({{
  doisD: {{
    nos: run.nos.map((n) => n.id),
    arestas: run.arestas.map((a) => [a.de, a.para]),
    lugares: [...posicionarNos(run)].map(([id, p]) => [id, p.x]),
  }},
  tresD: {{
    nos: trid.nodes.map((n) => n.id),
    arestas: trid.links.map((l) => [l.source, l.target]),
    z: trid.nodes.map((n) => [n.id, n.fz]),
    ondas: trid.nodes.map((n) => [n.id, n.onda]),
    estados: trid.nodes.map((n) => [n.id, n.estado]),
    chaves: [...new Set(trid.nodes.flatMap((n) => Object.keys(n)))].sort(),
  }},
}}));
"""
    return _no_navegador(script, {"eventos": eventos, "nos": nos, "arestas": arestas})


# ---------------------------------------------------------------------------
# 1 — a mesma topologia nos dois renderizadores
# ---------------------------------------------------------------------------


def test_3d_e_2d_desenham_o_mesmo_grafo_da_mesma_run() -> None:
    """O critério de aceite, literal."""
    saida = _projetado(_eventos())

    assert saida["tresD"]["nos"] == saida["doisD"]["nos"]
    assert saida["tresD"]["arestas"] == saida["doisD"]["arestas"]


def test_a_topologia_dos_dois_e_a_que_o_dados_emitiu(tmp_path: Path) -> None:
    """E ambas são a de `/dados`, não uma terceira coisa que casa por acaso."""
    eventos = _eventos()
    log = tmp_path / "log.jsonl"
    log.write_text("\n".join(json.dumps(ev) for ev in eventos) + "\n", encoding="utf-8")

    do_endpoint = dados_painel(log)["runs"][0]
    saida = _projetado(eventos)

    assert saida["tresD"]["nos"] == [no["id"] for no in do_endpoint["nos"]]
    assert saida["tresD"]["arestas"] == [
        [a["de"], a["para"]] for a in do_endpoint["arestas"]
    ]


def test_o_3d_nao_reprojeta_estado_a_partir_dos_eventos() -> None:
    """A segunda projeção de estado foi APAGADA, não portada.

    A página `/grafo3d` antiga tinha um ``switch`` próprio sobre os eventos para
    colorir nó — mais fraco que o `projetar.js`, porque não conhecia a
    classificação do andon. `B` falhou por ``executor.erro``; o estado tem de
    vir de lá, não de uma releitura local.
    """
    saida = _projetado(_eventos())
    estados = dict(saida["tresD"]["estados"])

    assert estados["B"] == "falhou"
    assert estados["A"] == "sem-portao"


# ---------------------------------------------------------------------------
# 2 — a posição não é inventada
# ---------------------------------------------------------------------------


def test_z_vem_da_onda_declarada_e_nao_da_fisica() -> None:
    saida = _projetado(_eventos())
    z = dict(saida["tresD"]["z"])
    ondas = dict(saida["tresD"]["ondas"])

    # Mesma onda -> mesmo Z, sempre.
    assert ondas["B"] == ondas["C"]
    assert z["B"] == z["C"]

    # Ondas diferentes -> Z diferente, nunca colidem.
    por_onda: dict[int, set] = {}
    for no, onda in ondas.items():
        por_onda.setdefault(onda, set()).add(z[no])
    assert all(len(zs) == 1 for zs in por_onda.values())
    assert len({zs.pop() for zs in por_onda.values()}) == len(por_onda)


def test_o_eixo_da_onda_e_o_mesmo_nas_duas_superficies() -> None:
    """No 2D a onda é o X (`x = onda * COLUNA`); no 3D é o Z. A ORDEM é a mesma.

    Se um renderizador ordenasse as ondas ao contrário do outro, os dois
    mostrariam o mesmo grafo contando histórias opostas sobre o que veio antes.
    """
    saida = _projetado(_eventos())
    x = dict(saida["doisD"]["lugares"])
    z = dict(saida["tresD"]["z"])

    ordem_2d = sorted(x, key=lambda no: (x[no], no))
    ordem_3d = sorted(z, key=lambda no: (z[no], no))
    assert ordem_2d == ordem_3d


def test_x_e_y_ficam_livres_para_a_fisica() -> None:
    """Só o Z é declarado. Fixar X ou Y seria afirmar posição que não existe."""
    chaves = _projetado(_eventos())["tresD"]["chaves"]

    assert "fz" in chaves
    assert "fx" not in chaves
    assert "fy" not in chaves
