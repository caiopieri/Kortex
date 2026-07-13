import json
import multiprocessing
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from motor.orcamento import (
    ErroOrcamento,
    RepositorioOrcamento,
    ReservaOrcamento,
)


def _concorrente_claim(raiz_str: str, owner: str) -> str | None:
    """Helper top-level para reivindicar pendente em subprocesso spawn."""
    repo = RepositorioOrcamento(Path(raiz_str))
    res = repo.reivindicar_pendente("run_conc", owner, 10, 5)
    return res.owner if res else None


def test_migracao_h12b2a_listar_pendentes_primeira_operacao(tmp_path):
    repo = RepositorioOrcamento(tmp_path)
    caminho = repo.caminho("run")

    with sqlite3.connect(caminho) as con:
        con.execute("DROP TABLE IF EXISTS budget_session")
        con.execute("DROP TABLE IF EXISTS budget_reservation")
        con.execute("DROP TABLE IF EXISTS budget_outbox")
        con.execute("DROP TABLE IF EXISTS budget_outbox_claim")
        con.execute("""
            CREATE TABLE budget_outbox (
                event_id TEXT PRIMARY KEY, reservation_id TEXT NOT NULL,
                tipo TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(reservation_id, tipo)
            )
        """)
        payload = {
            "run_id": "run",
            "thread_id": "thread",
            "call_id": "call",
            "rota": "rota",
            "tentativa": 1,
            "moeda": "BRL",
            "teto": "2",
            "gasto": "0",
            "reservado": "1",
            "reservation_id": "res",
            "maximo": "1",
            "pricing_version": "price-v1",
        }
        con.execute(
            "INSERT INTO budget_outbox VALUES (?, ?, ?, ?)",
            (
                repo._event_id("res", "custo.reservado"),
                "res",
                "custo.reservado",
                json.dumps(payload),
            ),
        )
        con.commit()

    res = repo.listar_pendentes("run")
    assert len(res) == 1
    assert res[0].event_id == repo._event_id("res", "custo.reservado")
    assert res[0].payload["reservation_id"] == "res"


def test_tentativas_overflow_inteiro_sqlite(tmp_path):
    """(2) RED: tentativas=2**63-1 levanta OverflowError em Python em vez de ErroOrcamento."""
    repo = RepositorioOrcamento(tmp_path)
    caminho = repo.caminho("run")
    sessao = repo.sessao("run", "thread", Decimal("2.0"))
    reserva = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar_exclusiva(sessao, reserva)

    event_id = repo._event_id("r1", "custo.reservado")
    with sqlite3.connect(caminho) as con:
        con.execute("PRAGMA ignore_check_constraints=ON")
        con.execute(
            "INSERT OR REPLACE INTO budget_outbox_claim VALUES (?, 'PENDING', NULL, NULL, ?)",
            (event_id, 2**63 - 1),
        )
        con.commit()

    with pytest.raises(ErroOrcamento):
        repo.reivindicar_pendente("run", "owner-a", 10, 5)
    with sqlite3.connect(caminho) as con:
        assert con.execute(
            "SELECT estado,owner,lease_ate,tentativas FROM budget_outbox_claim"
        ).fetchone() == ("PENDING", None, None, 2**63 - 1)


def test_fault_injection_trigger_claim_rollback(tmp_path):
    """(3) Fault injection via triggers no budget_outbox_claim garante rollback e ErroOrcamento."""
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2.0"))
    reserva = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar_exclusiva(sessao, reserva)

    caminho = repo.caminho("run")
    with sqlite3.connect(caminho) as con:
        con.execute("""
            CREATE TRIGGER fault_claim BEFORE UPDATE ON budget_outbox_claim
            BEGIN SELECT RAISE(ABORT, 'injected fault'); END
        """)
        con.commit()

    with pytest.raises(ErroOrcamento):
        repo.reivindicar_pendente("run", "owner-a", 10, 5)

    # O trigger bloqueou o update de claim, então o owner deve continuar nulo
    pendente = repo.listar_pendentes("run")[0]
    assert pendente.owner is None
    assert pendente.tentativas == 0


def test_concorrencia_multiprocessing_claim_exclusivo(tmp_path):
    """(4) Concorrência multiprocessing spawn garante um único claim vencedor e tentativas=1."""
    ctx = multiprocessing.get_context("spawn")
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run_conc", "thread", Decimal("2.0"))
    reserva = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar_exclusiva(sessao, reserva)

    # Força a criação do claim PENDING inicial no banco antes do paralelismo
    repo.listar_pendentes("run_conc")

    raiz_str = str(tmp_path)
    with ctx.Pool(2) as pool:
        resultados = pool.starmap(
            _concorrente_claim, [(raiz_str, "p1"), (raiz_str, "p2")]
        )

    assert sorted([str(r) for r in resultados]) == [
        "None",
        "p1" if resultados[0] == "p1" else "p2",
    ]

    with sqlite3.connect(repo.caminho("run_conc")) as con:
        claim = con.execute(
            "SELECT estado, owner, tentativas FROM budget_outbox_claim"
        ).fetchone()
        assert claim == ("CLAIMED", next(r for r in resultados if r), 1)
        assert con.execute("SELECT count(*) FROM budget_outbox").fetchone() == (1,)
        assert con.execute("SELECT count(*) FROM budget_outbox_claim").fetchone() == (1,)


def test_ack_versus_reclaim_limite_estado_unico(tmp_path):
    """(5) Corrida de confirmação (ack) de owner antigo versus reinvidicação (reclaim) no limite."""
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2.0"))
    reserva = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar_exclusiva(sessao, reserva)

    ev = repo.reivindicar_pendente("run", "owner-old", 90, 10)
    assert ev is not None

    ev_new = repo.reivindicar_pendente("run", "owner-new", 100, 10)
    assert ev_new is not None
    assert ev_new.owner == "owner-new"

    with pytest.raises(ErroOrcamento, match="claim invalido"):
        repo.confirmar_pendente("run", ev.event_id, "owner-old")


def test_confirmacoes_invalidas_nao_alteram_estado(tmp_path):
    """(6) Confirmações inválidas (ACK repetido/owner incorreto) não alteram tentativas ou estado."""
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2.0"))
    reserva = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar_exclusiva(sessao, reserva)

    ev = repo.reivindicar_pendente("run", "owner-a", 10, 5)
    assert ev is not None

    with pytest.raises(ErroOrcamento):
        repo.confirmar_pendente("run", ev.event_id, "owner-incorreto")

    with pytest.raises(ErroOrcamento):
        repo.confirmar_pendente("run", "id-inexistente", "owner-a")

    repo.confirmar_pendente("run", ev.event_id, "owner-a")

    with pytest.raises(ErroOrcamento):
        repo.confirmar_pendente("run", ev.event_id, "owner-a")

    with sqlite3.connect(repo.caminho("run")) as con:
        claim = con.execute(
            "SELECT estado, tentativas FROM budget_outbox_claim"
        ).fetchone()
        assert claim == ("ACKED", 1)


def test_dados_corrompidos_falham_fechado(tmp_path):
    """(7) Payload ou estado de claim corrompidos em banco devem falhar fechado nas leituras."""
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2.0"))
    reserva = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar_exclusiva(sessao, reserva)

    caminho = repo.caminho("run")
    event_id = repo._event_id("r1", "custo.reservado")

    # Caso A: tentativas negativas
    with sqlite3.connect(caminho) as con:
        con.execute("PRAGMA ignore_check_constraints=ON")
        con.execute(
            "INSERT OR REPLACE INTO budget_outbox_claim VALUES (?, 'CLAIMED', 'owner-a', 9999, -5)",
            (event_id,),
        )
        con.commit()
    with pytest.raises(ErroOrcamento, match="outbox corrompida"):
        repo.listar_pendentes("run")

    # Caso B: estado ilegal
    with sqlite3.connect(caminho) as con:
        con.execute("PRAGMA ignore_check_constraints=ON")
        con.execute(
            "INSERT OR REPLACE INTO budget_outbox_claim VALUES (?, 'LIXO', NULL, NULL, 0)",
            (event_id,),
        )
        con.commit()
    with pytest.raises(ErroOrcamento, match="outbox corrompida"):
        repo.listar_pendentes("run")
