from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from motor.eventos import LogEventos
from motor.orcamento import RepositorioOrcamento, ReservaOrcamento, publicar_um_pendente


def _repositorio(tmp_path: Path) -> RepositorioOrcamento:
    repositorio = RepositorioOrcamento(tmp_path / "runs")
    sessao = repositorio.sessao("run", "thread", Decimal("10"))
    reserva = ReservaOrcamento("reservation", "call", "route", 1, Decimal("1"), "v1")
    assert repositorio.reservar_exclusiva(sessao, reserva).status == "NOVA"
    return repositorio


def _eventos(path: Path) -> list[dict[str, object]]:
    return [json.loads(linha) for linha in path.read_text().splitlines()]


def test_relay_persiste_no_ledger_real_antes_do_ack(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)

    assert publicar_um_pendente(
        repositorio, "run", "worker", 10, 5, log.publicar_orcamento
    )
    log.fechar()

    assert repositorio.listar_pendentes("run") == []
    evento = _eventos(path)[0]
    assert evento["event_id"] == repositorio._event_id("reservation", "custo.reservado")
    assert evento["evento"] == "custo.reservado"


def test_crash_depois_do_efeito_redelivera_sem_duplicar_ledger(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)
    path = tmp_path / "eventos.jsonl"
    confirmar = repositorio.confirmar_pendente

    def cair_antes_do_ack(_run_id: str, _event_id: str, _owner: str) -> None:
        raise RuntimeError("crash antes do ack")

    primeiro = LogEventos(path)
    repositorio.confirmar_pendente = cair_antes_do_ack  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="crash antes do ack"):
        publicar_um_pendente(
            repositorio, "run", "worker-a", 10, 5, primeiro.publicar_orcamento
        )
    primeiro.fechar()

    repositorio.confirmar_pendente = confirmar  # type: ignore[method-assign]
    segundo = LogEventos(path)
    assert publicar_um_pendente(
        repositorio, "run", "worker-b", 15, 5, segundo.publicar_orcamento
    )
    segundo.fechar()

    assert len(_eventos(path)) == 1
    assert repositorio.listar_pendentes("run") == []


def test_redelivery_divergente_falha_sem_ack_ou_vazamento(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)
    evento = repositorio.reivindicar_pendente("run", "worker", 10, 5)
    assert evento is not None
    log.publicar_orcamento(evento.event_id, evento.tipo, evento.payload)

    divergente = {**evento.payload, "run_id": "outro"}
    with pytest.raises(ValueError, match="redelivery divergente"):
        log.publicar_orcamento(evento.event_id, evento.tipo, divergente)
    log.fechar()

    assert len(_eventos(path)) == 1
    assert repositorio.listar_pendentes("run")[0].owner == "worker"

    hostil = {**evento.payload, "segredo": "SEGREDO-NAO-PERSISTIR"}
    with pytest.raises(ValueError, match="fora do schema"):
        log = LogEventos(tmp_path / "hostil.jsonl")
        try:
            log.publicar_orcamento(evento.event_id, evento.tipo, hostil)
        finally:
            log.fechar()
    assert "SEGREDO-NAO-PERSISTIR" not in (tmp_path / "hostil.jsonl").read_text()


def test_publicacao_concorrente_deduplica_por_event_id(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)
    evento = repositorio.listar_pendentes("run")[0]
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(
            executor.map(
                lambda _: log.publicar_orcamento(evento.event_id, evento.tipo, evento.payload),
                range(2),
            )
        )
    log.fechar()

    assert len(_eventos(path)) == 1
