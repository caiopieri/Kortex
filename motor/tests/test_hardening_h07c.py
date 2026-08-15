from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path

import pytest

import motor.eventos as eventos_mod
from motor.eventos import LogEventos
from motor.eventos_schema import valido


def _evento(seq: int = 1) -> bytes:
    evento = {"t": 0, "seq": seq, "evento": "tarefa.concluida", "missao": "teste"}
    return (json.dumps(evento) + "\n").encode()


def test_sidecar_impede_split_brain_apos_replace_do_log(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    primeiro = LogEventos(path)
    primeiro.evento("tarefa.concluida", missao="inode-antigo")
    substituto = tmp_path / "substituto.jsonl"
    substituto.write_bytes(_evento())
    os.replace(substituto, path)

    with pytest.raises(RuntimeError, match="writer ativo"):
        LogEventos(path)

    primeiro.fechar()
    segundo = LogEventos(path)
    segundo.fechar()


def test_conflito_no_lock_do_log_libera_sidecar_novo(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    primeiro = LogEventos(path)
    primeiro._lock_path.unlink()

    with pytest.raises(RuntimeError, match="writer ativo"):
        LogEventos(path)

    primeiro.fechar()
    terceiro = LogEventos(path)
    terceiro.fechar()


@pytest.mark.parametrize("tipo_link", ["symlink", "hardlink"])
def test_log_recusa_links_sem_modificar_alvo(tmp_path: Path, tipo_link: str) -> None:
    vitima = tmp_path / "vitima.jsonl"
    alias = tmp_path / "eventos.jsonl"
    original = _evento() + b'{"tail":'
    vitima.write_bytes(original)
    if tipo_link == "symlink":
        alias.symlink_to(vitima)
    else:
        os.link(vitima, alias)

    with pytest.raises(ValueError, match="arquivo nao regular|hardlink"):
        LogEventos(alias)

    assert vitima.read_bytes() == original


def test_log_recusa_fifo_sem_abri_lo(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    os.mkfifo(path)

    with pytest.raises(ValueError, match="arquivo nao regular"):
        LogEventos(path)

    assert stat.S_ISFIFO(path.lstat().st_mode)


def test_criacao_sincroniza_entrada_no_diretorio(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_fsync = eventos_mod.os.fsync
    tipos: list[str] = []

    def registrar(fd: int) -> None:
        tipos.append("dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
        real_fsync(fd)

    monkeypatch.setattr(eventos_mod.os, "fsync", registrar)
    log = LogEventos(tmp_path / "eventos.jsonl")
    log.fechar()

    assert "file" in tipos
    assert "dir" in tipos


def test_falha_ao_abrir_log_libera_lock_do_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "eventos.jsonl"
    abrir_real = eventos_mod._abrir_regular_sem_links
    chamadas = 0

    def falhar_segunda_abertura(path_alvo: Path, flags: int) -> tuple[int, bool]:
        nonlocal chamadas
        chamadas += 1
        if chamadas == 2:
            raise OSError("open log")
        return abrir_real(path_alvo, flags)

    monkeypatch.setattr(eventos_mod, "_abrir_regular_sem_links", falhar_segunda_abertura)
    with pytest.raises(OSError, match="open log"):
        LogEventos(path)

    monkeypatch.setattr(eventos_mod, "_abrir_regular_sem_links", abrir_real)
    segundo = LogEventos(path)
    segundo.fechar()


def test_falha_de_unlock_ainda_fecha_log_e_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)
    real_flock = eventos_mod.fcntl.flock

    def falhar_unlock(fd: int, operacao: int) -> None:
        if operacao == eventos_mod.fcntl.LOCK_UN:
            raise OSError("unlock")
        real_flock(fd, operacao)

    monkeypatch.setattr(eventos_mod.fcntl, "flock", falhar_unlock)
    with pytest.raises(OSError, match="unlock"):
        log.fechar()
    assert log._f.closed
    assert log._lock_f.closed

    monkeypatch.setattr(eventos_mod.fcntl, "flock", real_flock)
    segundo = LogEventos(path)
    segundo.fechar()


def test_falha_de_write_fsync_libera_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)
    real_fsync = eventos_mod.os.fsync

    def falhar(_fd: int) -> None:
        raise OSError("fsync")

    monkeypatch.setattr(eventos_mod.os, "fsync", falhar)

    with pytest.raises(OSError, match="fsync"):
        log.evento("tarefa.concluida", missao="incerta")
    assert log._f.closed
    assert log._lock_f.closed

    monkeypatch.setattr(eventos_mod.os, "fsync", real_fsync)
    segundo = LogEventos(path)
    segundo.fechar()


@pytest.mark.parametrize("seq", [0, -1, True, 1.0])
def test_schema_v2_exige_seq_inteiro_real_positivo(seq: object) -> None:
    evento = {"t": 0, "evento": "tarefa.concluida", "missao": "teste", "seq": seq}
    assert not valido(evento)


def test_schema_v2_exige_seq_presente() -> None:
    evento = {"t": 0, "evento": "tarefa.concluida", "missao": "teste"}
    assert not valido(evento)
    assert valido({**evento, "seq": 1})


def test_writer_serializa_emissoes_concorrentes_e_reabre(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)
    barreira = threading.Barrier(8)

    def emitir(indice: int) -> None:
        barreira.wait()
        for numero in range(20):
            log.evento("tarefa.concluida", missao=f"{indice}-{numero}")

    threads = [threading.Thread(target=emitir, args=(indice,)) for indice in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert all(not thread.is_alive() for thread in threads)
    log.fechar()
    eventos = [json.loads(linha) for linha in path.read_text().splitlines()]
    assert [evento["seq"] for evento in eventos] == list(range(1, 161))

    reaberto = LogEventos(path)
    reaberto.evento("tarefa.concluida", missao="retomada")
    reaberto.fechar()
    assert json.loads(path.read_text().splitlines()[-1])["seq"] == 161
