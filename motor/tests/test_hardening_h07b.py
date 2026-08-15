from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import motor.eventos as eventos_mod
from motor.eventos import LogEventos
from motor_painel.painel import parse_eventos


def _evento(seq: int, instante: float, missao: str) -> bytes:
    return json.dumps(
        {
            "t": instante,
            "seq": seq,
            "evento": "tarefa.concluida",
            "missao": missao,
        },
        separators=(",", ":"),
    ).encode()


def _eventos(path: Path) -> list[dict[str, Any]]:
    return [json.loads(linha) for linha in path.read_bytes().splitlines()]


def test_writer_quarentena_tail_exato_e_retoma_seq_t(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    prefixo = _evento(1, 7.5, "anterior") + b"\n"
    tail = b'\xff{"t":'
    path.write_bytes(prefixo + tail)

    log = LogEventos(path)
    log.evento("tarefa.concluida", missao="retomada")
    log.fechar()

    quarentenas = list(tmp_path.glob("eventos.jsonl.tail-2*.quarentena"))
    assert len(quarentenas) == 1
    assert quarentenas[0].read_bytes() == tail
    assert path.read_bytes().startswith(prefixo)
    eventos = _eventos(path)
    assert [evento["seq"] for evento in eventos] == [1, 2]
    assert eventos[1]["t"] >= 7.5


def test_writer_nao_recupera_arquivo_somente_parcial(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    original = b'{"t":'
    path.write_bytes(original)

    with pytest.raises(ValueError, match="registro completo"):
        LogEventos(path)

    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.quarentena")) == []


def test_writer_nao_trunca_se_quarentena_nao_for_duravel(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "eventos.jsonl"
    original = _evento(1, 0, "anterior") + b'\n{"t":'
    path.write_bytes(original)
    monkeypatch.setattr(
        eventos_mod.os,
        "fsync",
        lambda _fd: (_ for _ in ()).throw(OSError("fsync")),
    )

    with pytest.raises(OSError, match="fsync"):
        LogEventos(path)

    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.quarentena")) == []


def test_writer_nao_recupera_v1_com_tail(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    original = b'{"t":0,"evento":"spec.recebida"}\n{"t":'
    path.write_bytes(original)

    with pytest.raises(ValueError, match="v1 e somente leitura"):
        LogEventos(path)

    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.quarentena")) == []


@pytest.mark.parametrize(
    "prefixo",
    [
        _evento(1, 0, "um") + b"\nnao-json\n",
        _evento(2, 0, "gap") + b"\n",
        _evento(1, 2, "um") + b"\n" + _evento(2, 1, "regressao") + b"\n",
    ],
)
def test_writer_nao_recupera_prefixo_corrompido(
    tmp_path: Path,
    prefixo: bytes,
) -> None:
    path = tmp_path / "eventos.jsonl"
    original = prefixo + b'{"t":'
    path.write_bytes(original)

    with pytest.raises(ValueError):
        LogEventos(path)

    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.quarentena")) == []


def test_painel_preserva_v1_antes_do_tail_sem_newline(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    evento = {"t": 0, "evento": "spec.recebida"}
    path.write_bytes(json.dumps(evento).encode() + b'\n\xff{"t":')

    assert parse_eventos(path) == [evento]


@pytest.mark.parametrize(
    "conteudo",
    [
        b"nao-json\n",
        b'{"t":0,"evento":"spec.recebida"}\nnao-json\ntail',
        b'{"t":0,"evento":"spec.recebida"}\n\xff\ntail',
    ],
)
def test_painel_nao_mascara_corrupcao_completa_ou_intermediaria(
    tmp_path: Path,
    conteudo: bytes,
) -> None:
    path = tmp_path / "eventos.jsonl"
    path.write_bytes(conteudo)

    with pytest.raises((UnicodeDecodeError, json.JSONDecodeError)):
        parse_eventos(path)


def test_painel_ignora_arquivo_somente_parcial(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    path.write_bytes(b'\xff{"t":')

    assert parse_eventos(path) == []
