import sqlite3
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from motor.orcamento import ErroOrcamento, RepositorioOrcamento, ReservaOrcamento


def _reserva(nome: str = "r", maximo: str = "1") -> ReservaOrcamento:
    return ReservaOrcamento(nome, "call", "rota", 1, Decimal(maximo), "price-v1")


def test_reserva_nova_commita_outbox_com_snapshot(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao, reserva = repo.sessao("run", "thread", Decimal("2")), _reserva()
    assert repo.reservar_exclusiva(sessao, reserva).status == "NOVA"
    pendente = repo.listar_pendentes("run")
    assert [(e.tipo, e.payload) for e in pendente] == [("custo.reservado", {
        "run_id": "run", "thread_id": "thread", "call_id": "call", "rota": "rota",
        "tentativa": 1, "moeda": "BRL", "teto": "2", "gasto": "0", "reservado": "1",
        "reservation_id": "r", "maximo": "1", "pricing_version": "price-v1",
    })]
    with sqlite3.connect(repo.caminho("run")) as con:
        assert con.execute("SELECT gasto,reservado FROM budget_session").fetchone() == ("0", "1")


def test_falha_antes_do_commit_nao_deixa_reserva_nem_outbox(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2"))
    with sqlite3.connect(repo.caminho("run")) as con:
        con.execute("""CREATE TRIGGER falhar_outbox BEFORE INSERT ON budget_outbox
                       BEGIN SELECT RAISE(ABORT, 'falha injetada'); END""")
    with pytest.raises(ErroOrcamento):
        repo.reservar_exclusiva(sessao, _reserva())
    with sqlite3.connect(repo.caminho("run")) as con:
        assert con.execute("SELECT count(*) FROM budget_reservation").fetchone() == (0,)
        assert con.execute("SELECT count(*) FROM budget_outbox").fetchone() == (0,)


def test_replay_reserved_e_ambiguo_sem_outbox_duplicada(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao, reserva = repo.sessao("run", "thread", Decimal("2")), _reserva()
    assert repo.reservar_exclusiva(sessao, reserva).status == "NOVA"
    assert repo.reservar_exclusiva(sessao, reserva).status == "REPLAY_AMBIGUO"
    assert len(repo.listar_pendentes("run")) == 1
    assert repo.reservar(sessao, reserva).status == "RESERVED"  # compatibilidade H12b1


def test_teto_bloqueia_sem_reserva_e_persiste_snapshot(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("1"))
    assert repo.reservar_exclusiva(sessao, _reserva("r1")).status == "NOVA"
    resultado = repo.reservar_exclusiva(
        sessao, ReservaOrcamento("r2", "call-2", "rota", 1, Decimal("0.1"), "price-v1")
    )
    assert (resultado.status, resultado.motivo) == ("BLOQUEADA", "teto excedido")
    assert repo.listar_pendentes("run")[-1].payload == {
        "run_id": "run", "thread_id": "thread", "call_id": "call-2", "rota": "rota",
        "tentativa": 1, "moeda": "BRL", "teto": "1", "gasto": "0", "reservado": "1", "motivo": "teto",
    }


def test_reconciliacao_e_violacao_refletem_snapshot_do_sqlite(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao, reserva = repo.sessao("run", "thread", Decimal("3")), _reserva()
    repo.reservar(sessao, reserva)
    repo.reconciliar(sessao, reserva, Decimal("0.4"))
    reconciliado = repo.listar_pendentes("run")[-1].payload
    assert (reconciliado["gasto"], reconciliado["reservado"], reconciliado["delta_liberado"]) == ("0.4", "0", "0.6")
    sessao2, reserva2 = repo.sessao("run2", "thread", Decimal("2")), _reserva("r2")
    repo.reservar(sessao2, reserva2)
    repo.reconciliar(sessao2, reserva2, Decimal("3"))
    violado = repo.listar_pendentes("run2")[-1].payload
    assert (violado["gasto"], violado["reservado"], violado["motivo"]) == ("3", "0", "custo_acima_maximo")


def test_migracao_h12b1_e_concorrencia_exclusiva(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    caminho = repo.caminho("run")
    with sqlite3.connect(caminho) as con:
        con.execute("CREATE TABLE budget_session (run_id TEXT,thread_id TEXT,teto TEXT,moeda TEXT,gasto TEXT,reservado TEXT,status TEXT,PRIMARY KEY(run_id,thread_id))")
        con.execute("CREATE TABLE budget_reservation (reservation_id TEXT PRIMARY KEY,run_id TEXT,thread_id TEXT,call_id TEXT,route_id TEXT,attempt INTEGER,maximo TEXT,real TEXT,moeda_real TEXT,pricing_version TEXT,status TEXT,created_at TEXT,reconciled_at TEXT)")
    sessao = repo.sessao("run", "thread", Decimal("1"))
    assert repo.reservar_exclusiva(sessao, _reserva("m")).status == "NOVA"
    with ThreadPoolExecutor(max_workers=2) as pool:
        estados = list(pool.map(lambda nome: repo.reservar_exclusiva(
            repo.sessao("conc", "thread", Decimal("1")),
            ReservaOrcamento(nome, f"call-{nome}", "rota", 1, Decimal("1"), "price-v1")).status,
            ("a", "b")))
    assert estados.count("NOVA") == 1 and estados.count("BLOQUEADA") == 1
