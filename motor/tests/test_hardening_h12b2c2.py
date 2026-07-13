from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from motor.orcamento import (
    ErroOrcamento,
    RepositorioOrcamento,
    ReservaOrcamento,
    publicar_um_pendente,
)


def _repositorio(tmp_path: Path) -> RepositorioOrcamento:
    repositorio = RepositorioOrcamento(tmp_path)
    sessao = repositorio.sessao("run", "thread", Decimal("10"))
    reserva = ReservaOrcamento("reservation", "call", "route", 1, Decimal("1"), "v1")
    assert repositorio.reservar_exclusiva(sessao, reserva).status == "NOVA"
    return repositorio


def test_relay_publica_um_com_event_id_e_confirma(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)
    recebidos: list[tuple[str, str, dict[str, object]]] = []

    def publicador(event_id: str, tipo: str, payload: dict[str, object]) -> None:
        recebidos.append((event_id, tipo, payload))

    assert publicar_um_pendente(repositorio, "run", "worker", 10, 5, publicador) is True

    assert len(recebidos) == 1
    event_id, tipo, payload = recebidos[0]
    assert len(event_id) == 64
    assert tipo == "custo.reservado"
    assert payload["reservation_id"] == "reservation"
    assert repositorio.listar_pendentes("run") == []
    assert publicar_um_pendente(repositorio, "run", "worker", 10, 5, publicador) is False


def test_publicador_invalido_nao_reivindica(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)

    with pytest.raises(ErroOrcamento, match="publicador invalido"):
        publicar_um_pendente(repositorio, "run", "worker", 10, 5, object())  # type: ignore[arg-type]

    pendente = repositorio.listar_pendentes("run")[0]
    assert pendente.owner is None
    assert pendente.tentativas == 0


def test_excecao_nao_confirma_nem_persiste_segredo(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)

    def falhar(_event_id: str, _tipo: str, _payload: dict[str, object]) -> None:
        raise RuntimeError("SEGREDO-NAO-PERSISTIR")

    with pytest.raises(RuntimeError, match="SEGREDO-NAO-PERSISTIR"):
        publicar_um_pendente(repositorio, "run", "worker", 10, 5, falhar)

    pendente = repositorio.listar_pendentes("run")[0]
    assert pendente.owner == "worker"
    assert pendente.lease_ate == 15
    assert pendente.tentativas == 1
    with sqlite3.connect(repositorio.caminho("run")) as con:
        dump = "\n".join(con.iterdump())
    assert "SEGREDO-NAO-PERSISTIR" not in dump


def test_redelivery_apos_falha_de_ack_preserva_event_id(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)
    ids: list[str] = []
    confirmar = repositorio.confirmar_pendente

    def cair_antes_do_ack(_run_id: str, _event_id: str, _owner: str) -> None:
        raise RuntimeError("crash antes do ack")

    repositorio.confirmar_pendente = cair_antes_do_ack  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="crash antes do ack"):
        publicar_um_pendente(repositorio, "run", "worker-a", 10, 5, lambda event_id, _t, _p: ids.append(event_id))
    assert publicar_um_pendente(repositorio, "run", "worker-b", 14, 5, lambda *_: None) is False

    repositorio.confirmar_pendente = confirmar  # type: ignore[method-assign]
    assert publicar_um_pendente(repositorio, "run", "worker-b", 15, 5, lambda event_id, _t, _p: ids.append(event_id))
    assert ids == [ids[0], ids[0]]


def test_publicador_recebe_copia_defensiva(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)
    original = repositorio.reivindicar_pendente
    evento = original("run", "pre", 1, 1)
    assert evento is not None
    repositorio.reivindicar_pendente = lambda *_: evento  # type: ignore[method-assign]
    repositorio.confirmar_pendente = lambda *_: None  # type: ignore[method-assign]

    def alterar(_event_id: str, _tipo: str, payload: dict[str, object]) -> None:
        payload["reservation_id"] = "alterado"

    assert publicar_um_pendente(repositorio, "run", "worker", 10, 5, alterar)
    assert evento.payload["reservation_id"] == "reservation"


def test_concorrencia_publica_uma_unica_vez_antes_do_lease(tmp_path: Path) -> None:
    repositorio = _repositorio(tmp_path)
    publicados: list[str] = []

    def relay(owner: str) -> bool:
        return publicar_um_pendente(
            repositorio, "run", owner, 10, 20,
            lambda event_id, _tipo, _payload: publicados.append(event_id),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(relay, ("worker-a", "worker-b")))

    assert sorted(resultados) == [False, True]
    assert len(publicados) == 1
