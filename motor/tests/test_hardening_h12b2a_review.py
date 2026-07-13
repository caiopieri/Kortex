import json
import multiprocessing
import os
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from motor.eventos_schema import valido
from motor.orcamento import ErroOrcamento, RepositorioOrcamento, ReservaOrcamento


def _rodar_reserva_processo(raiz_str: str, res_id: str, maximo_str: str) -> str:
    """Helper top-level para rodar reserva exclusiva em processo spawn."""
    repo = RepositorioOrcamento(Path(raiz_str))
    sessao = repo.sessao("run_proc", "thread_proc", Decimal("2.0"))
    reserva = ReservaOrcamento(
        res_id, "call", "rota", 1, Decimal(maximo_str), "price-v1"
    )
    try:
        return repo.reservar_exclusiva(sessao, reserva).status
    except ErroOrcamento as erro:
        return f"ERRO:{erro}"


def test_colisao_outbox_payload_divergente_faz_rollback(tmp_path):
    """(1) RED: Colisão de outbox com payload divergente deve falhar e dar rollback."""
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("5.0"))
    reserva = ReservaOrcamento("r1", "call", "rota", 1, Decimal("1.0"), "price-v1")
    caminho = repo.caminho("run")
    event_id = repo._event_id("r1", "custo.reservado")
    payload_divergente = {
        "run_id": "run",
        "thread_id": "thread",
        "call_id": "call",
        "rota": "rota",
        "tentativa": 1,
        "moeda": "BRL",
        "teto": "5.0",
        "gasto": "0",
        "reservado": "99.0",
        "reservation_id": "r1",
        "maximo": "1.0",
        "pricing_version": "price-v1",
    }
    with sqlite3.connect(caminho) as con:
        con.execute(
            "INSERT INTO budget_outbox VALUES (?, ?, ?, ?)",
            (event_id, "r1", "custo.reservado", json.dumps(payload_divergente)),
        )
        con.commit()
    with pytest.raises(ErroOrcamento, match="colisao outbox|payload divergente"):
        repo.reservar_exclusiva(sessao, reserva)
    with sqlite3.connect(caminho) as con:
        reservado = con.execute("SELECT reservado FROM budget_session").fetchone()[0]
        assert Decimal(reservado) == Decimal("0")


def test_payloads_produzidos_validados_pelo_esquema(tmp_path):
    """(2) Todo payload produzido na outbox deve passar no eventos_schema.valido."""
    repo = RepositorioOrcamento(tmp_path)
    # 1. Reserva & Reconciliado
    sessao1 = repo.sessao("run1", "thread1", Decimal("5.0"))
    reserva1 = ReservaOrcamento("r1", "call1", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar_exclusiva(sessao1, reserva1)
    repo.reconciliar(sessao1, reserva1, Decimal("0.4"))
    # 2. Bloqueio por teto
    sessao2 = repo.sessao("run2", "thread2", Decimal("1.0"))
    reserva2a = ReservaOrcamento("r2a", "call2a", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar_exclusiva(sessao2, reserva2a)
    reserva2b = ReservaOrcamento("r2b", "call2b", "rota", 1, Decimal("0.5"), "price-v1")
    repo.reservar_exclusiva(sessao2, reserva2b)
    # 3. Custo acima do máximo
    sessao3 = repo.sessao("run3", "thread3", Decimal("5.0"))
    reserva3 = ReservaOrcamento("r3", "call3", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar(sessao3, reserva3)
    repo.reconciliar(sessao3, reserva3, Decimal("2.0"))
    # 4. Moeda divergente
    sessao4 = repo.sessao("run4", "thread4", Decimal("5.0"))
    reserva4 = ReservaOrcamento("r4", "call4", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar(sessao4, reserva4)
    repo.reconciliar(sessao4, reserva4, Decimal("1.0"), "USD")
    # 5. Custo inválido
    sessao5 = repo.sessao("run5", "thread5", Decimal("5.0"))
    reserva5 = ReservaOrcamento("r5", "call5", "rota", 1, Decimal("1.0"), "price-v1")
    repo.reservar(sessao5, reserva5)
    repo.reconciliar(sessao5, reserva5, None)

    runs = ["run1", "run2", "run3", "run4", "run5"]
    todas_pendentes = []
    for r in runs:
        todas_pendentes.extend(repo.listar_pendentes(r))
    for i, e in enumerate(todas_pendentes):
        evento_completo = {
            "evento": e.tipo,
            "t": 123456789.0,
            "seq": i + 1,
            **e.payload,
        }
        assert valido(evento_completo) is True


def test_concorrencia_exclusiva_processos_mac_spawn(tmp_path):
    """(3) Prova estado físico e outbox após concorrência multiprocessing spawn."""
    ctx = multiprocessing.get_context("spawn")
    # Inicializa sessão para os subprocessos lerem sem criar ao mesmo tempo
    repo = RepositorioOrcamento(tmp_path)
    repo.sessao("run_proc", "thread_proc", Decimal("2.0"))

    raiz_str = str(tmp_path)
    with ctx.Pool(2) as pool:
        resultados = pool.starmap(
            _rodar_reserva_processo, [(raiz_str, "r1", "1.0"), (raiz_str, "r1", "1.0")]
        )
    # Um deve ser NOVA e outro REPLAY_AMBIGUO
    assert sorted(resultados) == ["NOVA", "REPLAY_AMBIGUO"]

    caminho = repo.caminho("run_proc")
    with sqlite3.connect(caminho) as con:
        reservas = con.execute(
            "SELECT reservation_id, status FROM budget_reservation"
        ).fetchall()
        outbox = con.execute("SELECT tipo, payload FROM budget_outbox").fetchall()
        reservado = con.execute("SELECT reservado FROM budget_session").fetchone()[0]
        # Exatamente 1 reserva, 1 outbox e saldo de reserva exato
        assert len(reservas) == 1
        assert len(outbox) == 1
        assert Decimal(reservado) == Decimal("1.0")
        assert json.loads(outbox[0][1])["reservado"] == "1"


def test_migracao_reforcada_h12b1_outbox_e_constraints(tmp_path):
    """(4) Migração de H12b1 para H12b2a preserva dados antigos e cria índices UNIQUE reais."""
    caminho_dir = tmp_path / "run1"
    caminho_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    caminho_db = caminho_dir / "orcamento.sqlite3"
    con = sqlite3.connect(caminho_db)
    con.executescript("""
        CREATE TABLE budget_session (
          run_id TEXT NOT NULL, thread_id TEXT NOT NULL, teto TEXT NOT NULL, moeda TEXT NOT NULL,
          gasto TEXT NOT NULL, reservado TEXT NOT NULL, status TEXT NOT NULL,
          PRIMARY KEY (run_id, thread_id), CHECK (moeda='BRL'), CHECK (status IN ('ACTIVE','INVALIDATED')));
        CREATE TABLE budget_reservation (
          reservation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, thread_id TEXT NOT NULL,
          call_id TEXT NOT NULL, route_id TEXT NOT NULL, attempt INTEGER NOT NULL, maximo TEXT NOT NULL,
          real TEXT, moeda_real TEXT, pricing_version TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT, reconciled_at TEXT,
          UNIQUE (run_id,thread_id,call_id,route_id,attempt),
          FOREIGN KEY (run_id,thread_id) REFERENCES budget_session(run_id,thread_id));
    """)
    con.execute(
        "INSERT INTO budget_session VALUES ('run1', 'thread1', '2', 'BRL', '0', '0', 'ACTIVE')"
    )
    con.execute(
        "INSERT INTO budget_reservation VALUES ('r_old', 'run1', 'thread1', 'call_old', 'rota', 1, '1', NULL, NULL, 'price-v1', 'RESERVED', NULL, NULL)"
    )
    con.commit()
    con.close()
    os.chmod(caminho_db, 0o600)

    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run1", "thread1", Decimal("2.0"))
    assert sessao.teto == Decimal("2")
    assert sessao.status == "ACTIVE"

    # Valida índices UNIQUE reais via PRAGMA
    with sqlite3.connect(caminho_db) as con:
        assert con.execute(
            "SELECT reservation_id,status FROM budget_reservation"
        ).fetchall() == [("r_old", "RESERVED")]
        # budget_reservation UNIQUE (run_id, thread_id, call_id, route_id, attempt)
        indices_res = con.execute("PRAGMA index_list(budget_reservation)").fetchall()
        uniques_res = [idx[1] for idx in indices_res if idx[2] == 1]
        cols_res = []
        for name in uniques_res:
            cols = [
                col[2] for col in con.execute(f"PRAGMA index_info({name})").fetchall()
            ]
            if set(cols) == {"run_id", "thread_id", "call_id", "route_id", "attempt"}:
                cols_res = cols
        assert len(cols_res) == 5

        # budget_outbox UNIQUE (reservation_id, tipo)
        indices_out = con.execute("PRAGMA index_list(budget_outbox)").fetchall()
        uniques_out = [idx[1] for idx in indices_out if idx[2] == 1]
        cols_out = []
        for name in uniques_out:
            cols = [
                col[2] for col in con.execute(f"PRAGMA index_info({name})").fetchall()
            ]
            if set(cols) == {"reservation_id", "tipo"}:
                cols_out = cols
        assert len(cols_out) == 2


def test_leitura_falha_fechada_para_payload_fora_do_schema(tmp_path):
    """(5) RED: Leitura (listar_pendentes) deve falhar fechada para payload JSON estruturalmente válido mas inválido no schema."""
    repo = RepositorioOrcamento(tmp_path)
    repo.sessao("run", "thread", Decimal("5.0"))
    caminho = repo.caminho("run")
    event_id = repo._event_id("r1", "custo.reservado")
    payload_invalido = {
        "run_id": 12345,
        "thread_id": "thread",
        "call_id": "call",
        "rota": "rota",
        "tentativa": "lixo",
        "moeda": "USD",
    }
    with sqlite3.connect(caminho) as con:
        con.execute(
            "INSERT INTO budget_outbox VALUES (?, ?, ?, ?)",
            (event_id, "r1", "custo.reservado", json.dumps(payload_invalido)),
        )
        con.commit()
    with pytest.raises(ErroOrcamento, match="outbox corrompida|payload invalido"):
        repo.listar_pendentes("run")
