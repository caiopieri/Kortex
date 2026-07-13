from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import motor.eventos as eventos_mod
from motor.eventos import LogEventos
from motor.eventos_schema import valido


def _linhas(path: Path) -> list[dict[str, Any]]:
    return [json.loads(linha) for linha in path.read_text().splitlines()]


def test_writer_v2_persiste_seq_e_tempo_apos_reabertura(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    relogio = iter([100.0, 101.0, 99.0, 200.0, 201.0])
    monkeypatch.setattr(eventos_mod.time, "monotonic", lambda: next(relogio))
    path = tmp_path / "eventos.jsonl"

    primeiro = LogEventos(path)
    primeiro.evento("tarefa.concluida", missao="um")
    primeiro.evento("tarefa.concluida", missao="dois")
    primeiro.fechar()
    segundo = LogEventos(path)
    segundo.evento("tarefa.concluida", missao="tres")
    segundo.fechar()

    eventos = _linhas(path)
    assert [evento["seq"] for evento in eventos] == [1, 2, 3]
    tempos = [evento["t"] for evento in eventos]
    assert tempos == sorted(tempos)
    assert tempos[0] == tempos[1]
    assert tempos[2] > tempos[1]


def test_lock_impede_segundo_writer_ate_o_primeiro_fechar(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    primeiro = LogEventos(path)

    with pytest.raises(RuntimeError, match="writer ativo"):
        LogEventos(path)

    primeiro.fechar()
    segundo = LogEventos(path)
    segundo.fechar()


def test_log_v1_permanece_read_only_e_inalterado(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    original = '{"t": 1, "evento": "tarefa.concluida", "missao": "legado"}\n'
    path.write_text(original)

    with pytest.raises(ValueError, match="v1 e somente leitura"):
        LogEventos(path)

    assert path.read_text() == original


@pytest.mark.parametrize(
    "conteudo",
    [
        "nao-json\n",
        (
            '{"t":0,"seq":1,"evento":"tarefa.concluida","missao":"um"}\n'
            "nao-json\n"
            '{"t":1,"seq":2,"evento":"tarefa.concluida","missao":"dois"}\n'
        ),
        '{"t":0,"seq":2,"evento":"tarefa.concluida","missao":"gap"}\n',
    ],
)
def test_corrupcao_completa_ou_intermediaria_falha_sem_alterar(
    tmp_path: Path,
    conteudo: str,
) -> None:
    path = tmp_path / "eventos.jsonl"
    path.write_text(conteudo)

    with pytest.raises(ValueError):
        LogEventos(path)

    assert path.read_text() == conteudo


def test_validacao_e_json_estrito_ocorrem_antes_do_write(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)

    with pytest.raises(ValueError):
        log.evento(
            "ferramenta.executada",
            ferramenta="pytest",
            subagente="executor",
            aprovado=True,
            metricas={"latencia": float("nan")},
        )
    assert path.read_text() == ""

    log.evento("tarefa.concluida", missao="valida")
    log.fechar()
    assert _linhas(path)[0]["seq"] == 1


def test_falha_de_fsync_fecha_writer_sem_avancar_estado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)
    monkeypatch.setattr(eventos_mod.os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError("fsync")))

    with pytest.raises(OSError, match="fsync"):
        log.evento("tarefa.concluida", missao="incerta")

    assert log._f.closed
    with pytest.raises(ValueError, match="closed file"):
        log.evento("tarefa.concluida", missao="nao duplica")


@pytest.mark.parametrize("instante", [-1, float("nan"), float("inf")])
def test_schema_v2_rejeita_tempo_invalido(instante: float) -> None:
    assert not valido(
        {
            "t": instante,
            "seq": 1,
            "evento": "tarefa.concluida",
            "missao": "teste",
        }
    )


def test_flag_legada_de_truncamento_nao_apaga_log_v2(tmp_path: Path) -> None:
    path = tmp_path / "eventos.jsonl"
    primeiro = LogEventos(path)
    primeiro.evento("tarefa.concluida", missao="um")
    primeiro.fechar()

    segundo = LogEventos(path, truncar=True)
    segundo.evento("tarefa.concluida", missao="dois")
    segundo.fechar()

    assert [evento["seq"] for evento in _linhas(path)] == [1, 2]
