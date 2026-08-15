from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, cast

import pytest

from motor_painel.painel import Handler, obter_gates_pendentes, parse_eventos


def _linha(evento: dict[str, Any]) -> bytes:
    return json.dumps(evento, separators=(",", ":")).encode() + b"\n"


def _pendente_v2(seq: int = 1, instante: float = 0) -> dict[str, Any]:
    return {
        "t": instante,
        "seq": seq,
        "evento": "decisao.pendente",
        "portao": "promocao",
        "nota": "revisar",
    }


def test_v1_permanece_visual_mas_nao_cria_gate(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    legado = {
        "t": 0,
        "evento": "decisao.pendente",
        "portao": "promocao",
        "nota": "legado",
        "opcoes": ["promover_sem_gate"],
    }
    path.write_bytes(_linha(legado))

    eventos = parse_eventos(path)
    assert eventos == [legado]
    assert obter_gates_pendentes(eventos) == []


def test_v1_nao_resolve_gate_v2(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    fundador_v1 = {
        "t": 1,
        "evento": "decisao.fundador",
        "portao": "promocao",
        "decisao": "prosseguir",
    }
    path.write_bytes(_linha(_pendente_v2()) + _linha(fundador_v1))

    assert [gate["portao"] for gate in obter_gates_pendentes(parse_eventos(path))] == [
        "promocao"
    ]

    fundador_v2 = {**fundador_v1, "t": 2, "seq": 2}
    path.write_bytes(path.read_bytes() + _linha(fundador_v2))
    assert obter_gates_pendentes(parse_eventos(path)) == []


def test_post_gate_v1_retorna_404_sem_criar_sqlite(tmp_path: Path) -> None:
    log_path = tmp_path / "eventos.jsonl"
    db_path = tmp_path / "caixa.db"
    log_path.write_bytes(
        _linha(
            {
                "t": 0,
                "evento": "decisao.pendente",
                "portao": "promocao",
                "nota": "legado",
            }
        )
    )
    corpo = json.dumps({"decisao": "prosseguir"}).encode()
    handler = cast(Any, object.__new__(Handler))
    handler.path = "/dados/gates/promocao"
    handler.headers = {"Content-Length": str(len(corpo))}
    handler.rfile = io.BytesIO(corpo)
    handler.wfile = io.BytesIO()
    handler.log_path = log_path
    handler.db_path = db_path
    status: list[int] = []
    handler.send_response = status.append
    handler.end_headers = lambda: None

    handler.do_POST()

    assert status == [404]
    assert not db_path.exists()


@pytest.mark.parametrize(
    "conteudo",
    [
        b'{"t":NaN,"seq":1,"evento":"tarefa.concluida","missao":"x"}\n',
        _linha({"t": 0, "seq": 1, "evento": "tarefa.concluida"}),
        _linha(
            {
                "t": 0,
                "seq": 1,
                "evento": "tarefa.concluida",
                "missao": "x",
                "extra": True,
            }
        ),
        _linha({"t": 0, "seq": 2, "evento": "tarefa.concluida", "missao": "x"}),
        _linha({"t": 0, "seq": 1, "evento": "tarefa.concluida", "missao": "x"})
        + _linha({"t": 1, "seq": 1, "evento": "tarefa.concluida", "missao": "y"}),
        _linha({"t": 0, "seq": 1, "evento": "tarefa.concluida", "missao": "x"})
        + _linha({"t": 1, "seq": 3, "evento": "tarefa.concluida", "missao": "y"}),
        _linha({"t": 2, "seq": 1, "evento": "tarefa.concluida", "missao": "x"})
        + _linha({"t": 1, "seq": 2, "evento": "tarefa.concluida", "missao": "y"}),
    ],
)
def test_v2_falha_fechado_em_corrupcao_semantica(
    tmp_path: Path, conteudo: bytes,
) -> None:
    path = tmp_path / "eventos.jsonl"
    path.write_bytes(conteudo)

    with pytest.raises(ValueError):
        parse_eventos(path)


def test_v2_ignora_somente_tail_final_sem_newline(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    pendente = _pendente_v2()
    path.write_bytes(_linha(pendente) + b'{"t":NaN')

    assert parse_eventos(path) == [pendente]
