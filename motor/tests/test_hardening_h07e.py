from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from motor.eventos import LogEventos


def _evento() -> bytes:
    evento = {"t": 0, "seq": 1, "evento": "tarefa.concluida", "missao": "novo"}
    return (json.dumps(evento) + "\n").encode()


def test_writer_falha_se_path_for_substituido_e_libera_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    primeiro = LogEventos(path)
    primeiro.evento("tarefa.concluida", missao="inode-antigo")
    substituto = tmp_path / "substituto.jsonl"
    esperado = _evento()
    substituto.write_bytes(esperado)
    os.replace(substituto, path)

    with pytest.raises(RuntimeError, match="substituido"):
        primeiro.evento("tarefa.concluida", missao="nao-pode-sumir")

    assert primeiro._f.closed
    assert primeiro._lock_f.closed
    assert path.read_bytes() == esperado
    segundo = LogEventos(path)
    segundo.fechar()


def test_writer_falha_se_path_desaparecer_e_libera_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    primeiro = LogEventos(path)
    path.unlink()

    with pytest.raises(RuntimeError, match="desapareceu"):
        primeiro.evento("tarefa.concluida", missao="perdida")

    assert primeiro._f.closed
    assert primeiro._lock_f.closed
    segundo = LogEventos(path)
    segundo.fechar()


def test_writer_recusa_hardlink_criado_depois_da_abertura(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    alias = tmp_path / "alias.jsonl"
    primeiro = LogEventos(path)
    primeiro.evento("tarefa.concluida", missao="persistida")
    original = path.read_bytes()
    os.link(path, alias)

    with pytest.raises(ValueError, match="hardlink"):
        primeiro.evento("tarefa.concluida", missao="recusada")

    assert primeiro._f.closed
    assert primeiro._lock_f.closed
    assert path.read_bytes() == original
    alias.unlink()
    segundo = LogEventos(path)
    segundo.fechar()
