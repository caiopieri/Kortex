import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from multiprocessing import get_context
from pathlib import Path

import pytest

from motor.orcamento import ErroOrcamento, RepositorioOrcamento, ReservaOrcamento


def _reservar(raiz: Path, run: str = "run") -> RepositorioOrcamento:
    repo = RepositorioOrcamento(raiz)
    sessao = repo.sessao(run, "thread", Decimal("2"))
    repo.reservar(sessao, ReservaOrcamento("res-1", "call-1", "rota", 1, Decimal("1"), "price-v1"))
    return repo


def _claim_processo(raiz: str, owner: str) -> str | None:
    evento = RepositorioOrcamento(Path(raiz)).reivindicar_pendente("run", owner, 10, 5)
    return None if evento is None else evento.event_id


def test_claim_thread_e_processo_sao_exclusivos(tmp_path: Path) -> None:
    repo = _reservar(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(lambda owner: repo.reivindicar_pendente("run", owner, 10, 5), ("a", "b")))
    assert sum(evento is not None for evento in resultados) == 1
    vencedor = next(evento for evento in resultados if evento is not None)
    assert vencedor.owner is not None
    repo.confirmar_pendente("run", vencedor.event_id, vencedor.owner)
    repo = _reservar(tmp_path / "processos")
    with get_context("spawn").Pool(2) as pool:
        resultados_processo = pool.starmap(_claim_processo, ((str(tmp_path / "processos"), "p1"), (str(tmp_path / "processos"), "p2")))
    assert sum(evento is not None for evento in resultados_processo) == 1


def test_cas_expiracao_restart_e_pendentes(tmp_path: Path) -> None:
    repo = _reservar(tmp_path)
    evento = repo.reivindicar_pendente("run", "owner-a", 100, 10)
    assert evento and repo.reivindicar_pendente("run", "owner-b", 109, 10) is None
    retomado = repo.reivindicar_pendente("run", "owner-b", 110, 10)
    assert retomado and retomado.event_id == evento.event_id and retomado.tentativas == 2
    with pytest.raises(ErroOrcamento):
        repo.confirmar_pendente("run", evento.event_id, "owner-a")
    repo.confirmar_pendente("run", evento.event_id, "owner-b")
    assert RepositorioOrcamento(tmp_path).listar_pendentes("run") == []


def test_migracao_real_e_colunas_corrompidas_falham_fechado(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    caminho = repo.caminho("run")
    payload = {"run_id": "run", "thread_id": "thread", "call_id": "call", "rota": "rota", "tentativa": 1, "moeda": "BRL", "teto": "2", "gasto": "0", "reservado": "1", "reservation_id": "res", "maximo": "1", "pricing_version": "price-v1"}
    with sqlite3.connect(caminho) as con:
        con.execute("CREATE TABLE budget_outbox (event_id TEXT PRIMARY KEY,reservation_id TEXT,tipo TEXT,payload TEXT,UNIQUE(reservation_id,tipo))")
        con.execute("INSERT INTO budget_outbox VALUES (?,?,?,?)", (repo._event_id("res", "custo.reservado"), "res", "custo.reservado", json.dumps(payload)))
    repo.sessao("run", "thread", Decimal("2"))
    pendente = repo.listar_pendentes("run")[0]
    assert (pendente.owner, pendente.lease_ate, pendente.tentativas) == (None, None, 0)
    with sqlite3.connect(caminho) as con:
        con.execute("PRAGMA ignore_check_constraints=ON")
        con.execute("UPDATE budget_outbox_claim SET owner='corrompido'")
    with pytest.raises(ErroOrcamento, match="outbox corrompida"):
        repo.listar_pendentes("run")


def test_inputs_e_estados_invalidos_falham_sem_mutacao(tmp_path: Path) -> None:
    repo = _reservar(tmp_path)
    with pytest.raises(ErroOrcamento):
        repo.reivindicar_pendente("run", "owner", True, 1)
    evento = repo.listar_pendentes("run")[0]
    with pytest.raises(ErroOrcamento):
        repo.confirmar_pendente("run", evento.event_id, "owner")
    assert len(repo.listar_pendentes("run")) == 1
