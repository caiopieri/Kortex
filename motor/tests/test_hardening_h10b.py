import multiprocessing
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from motor.caixa import LedgerCaixa


def _registrar(ledger: LedgerCaixa, *, decisao: str = "prosseguir") -> int:
    return ledger.registrar_decisao(decisao_id="decisao-1", job_id="job-1",
                                    portao="cobertura", decisao=decisao)


def _contagens(db_path: Path) -> tuple[int, int]:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT (SELECT count(*) FROM caixa_ledger), "
            "(SELECT count(*) FROM caixa_outbox)"
        ).fetchone()
    assert row is not None
    return row


def _crash_durante_outbox(db_path: str) -> None:
    ledger = LedgerCaixa(db_path, clock=lambda: 100.0)
    ledger._conn.create_function("crash_h10b", 0, lambda: os._exit(23))
    ledger._conn.execute(
        "CREATE TRIGGER crash_outbox BEFORE INSERT ON caixa_outbox "
        "BEGIN SELECT crash_h10b(); END"
    )
    _registrar(ledger)


def test_decisao_e_outbox_commitam_juntas_ou_rollback_total(tmp_path: Path) -> None:
    db_path = tmp_path / "caixa.db"
    ledger = LedgerCaixa(db_path, clock=lambda: 100.0)
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TRIGGER falha_outbox BEFORE INSERT ON caixa_outbox "
                     "BEGIN SELECT RAISE(ABORT, 'fault injection'); END")
    with pytest.raises(sqlite3.IntegrityError, match="fault injection"):
        _registrar(ledger)
    assert _contagens(db_path) == (0, 0)
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TRIGGER falha_outbox")
    outbox_id = _registrar(ledger)
    assert _registrar(ledger) == outbox_id
    assert _contagens(db_path) == (1, 1)
    with sqlite3.connect(db_path) as conn:
        payload = conn.execute("SELECT payload FROM caixa_outbox").fetchone()[0]
        versao = conn.execute("SELECT schema_version FROM caixa_meta").fetchone()[0]
        assert versao == 1
    assert payload == ('{"decisao":"prosseguir","decisao_id":"decisao-1",'
                       '"job_id":"job-1","portao":"cobertura"}')
    ledger.fechar()


def test_claim_concorrente_concede_no_maximo_um_lease_vivo(tmp_path: Path) -> None:
    db_path = tmp_path / "caixa.db"
    base = LedgerCaixa(db_path, clock=lambda: 100.0)
    _registrar(base)
    base.fechar()
    barreira = threading.Barrier(2)
    def tentar(owner: str):
        ledger = LedgerCaixa(db_path, clock=lambda: 100.0)
        barreira.wait()
        try:
            return ledger.claim(owner, lease_s=30)
        finally:
            ledger.fechar()
    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(tentar, ("worker-a", "worker-b")))
    vivos = [resultado for resultado in resultados if resultado is not None]
    assert len(vivos) == 1
    assert vivos[0]["lease_version"] == 1


def test_lease_vivo_nao_eh_roubado_expirado_eh_reclamado_com_cas(tmp_path: Path) -> None:
    db_path = tmp_path / "caixa.db"
    agora = [100.0]
    primeiro = LedgerCaixa(db_path, clock=lambda: agora[0])
    segundo = LedgerCaixa(db_path, clock=lambda: agora[0])
    _registrar(primeiro)
    claim_a = primeiro.claim("worker-a", lease_s=10)
    assert claim_a is not None
    agora[0] = 101.0
    renovado = primeiro.renovar_claim(claim_a["outbox_id"], "worker-a",
                                      lease_version=1, lease_s=1)
    assert renovado["lease_ate"] == claim_a["lease_ate"]
    agora[0] = 109.0
    assert segundo.claim("worker-b", lease_s=10) is None
    agora[0] = 110.0
    claim_b = segundo.claim("worker-b", lease_s=10)
    assert claim_b is not None
    assert (claim_b["lease_owner"], claim_b["lease_version"]) == ("worker-b", 3)
    with pytest.raises(ValueError, match="transição"):
        primeiro.renovar_claim(claim_a["outbox_id"], "worker-a",
                               lease_version=2, lease_s=10)
    primeiro.fechar()
    segundo.fechar()


def test_clock_eh_lido_depois_de_obter_lock_de_escrita(tmp_path: Path) -> None:
    db_path = tmp_path / "caixa.db"
    base = LedgerCaixa(db_path, clock=lambda: 100.0)
    _registrar(base)
    base.fechar()
    pronto, iniciar, begin_tentado, clock_lido = (threading.Event() for _ in range(4))
    agora = [100.0]

    def relogio() -> float:
        clock_lido.set()
        return agora[0]

    def disputar() -> dict:
        ledger = LedgerCaixa(db_path, clock=relogio)

        def rastrear(sql: str) -> None:
            if sql == "BEGIN IMMEDIATE":
                begin_tentado.set()

        ledger._conn.set_trace_callback(rastrear)
        pronto.set()
        iniciar.wait()
        try:
            resultado = ledger.claim("worker-a", lease_s=10)
            assert resultado is not None
            return resultado
        finally:
            ledger.fechar()

    with ThreadPoolExecutor(max_workers=1) as pool:
        futuro = pool.submit(disputar)
        assert pronto.wait(2)
        with sqlite3.connect(db_path, isolation_level=None) as bloqueio:
            bloqueio.execute("BEGIN IMMEDIATE")
            iniciar.set()
            assert begin_tentado.wait(2)
            assert not clock_lido.is_set()
            agora[0] = 200.0
            bloqueio.execute("COMMIT")
        assert futuro.result(timeout=2)["lease_ate"] == 210.0


@pytest.mark.parametrize("campo,valor", [
    ("decisao_id", "../fora"), ("job_id", ""), ("job_id", ".oculto")])
def test_ids_invalidos_falham_sem_escrever(tmp_path: Path, campo: str, valor: str) -> None:
    db_path = tmp_path / "caixa.db"
    ledger = LedgerCaixa(db_path)
    dados = dict(decisao_id="decisao-1", job_id="job-1", portao="cobertura",
                 decisao="prosseguir")
    dados[campo] = valor
    with pytest.raises(ValueError, match="inválido"):
        ledger.registrar_decisao(**dados)
    assert _contagens(db_path) == (0, 0)
    ledger.fechar()


def test_conflito_e_transicao_invalidos_preservam_ledger(tmp_path: Path) -> None:
    db_path = tmp_path / "caixa.db"
    ledger = LedgerCaixa(db_path, clock=lambda: 100.0)
    _registrar(ledger)
    claim = ledger.claim("worker-a", lease_s=30)
    assert claim is not None
    with pytest.raises(ValueError, match="conflita"):
        _registrar(ledger, decisao="abortar")
    with pytest.raises(ValueError, match="transição"):
        ledger.renovar_claim(claim["outbox_id"], "worker-b", lease_version=1, lease_s=10)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE caixa_outbox SET lease_version = 9223372036854775807")
    with pytest.raises(ValueError, match="transição"):
        ledger.renovar_claim(
            claim["outbox_id"], "worker-a", lease_version=2**63 - 1, lease_s=10
        )
    assert _contagens(db_path) == (1, 1)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT l.decisao, o.lease_owner, typeof(o.lease_version) "
                           "FROM caixa_ledger l JOIN caixa_outbox o "
                           "USING (decisao_id)").fetchone()
    assert row == ("prosseguir", "worker-a", "integer")
    ledger.fechar()


def test_reabertura_preserva_ledger_e_outbox(tmp_path: Path) -> None:
    db_path = tmp_path / "caixa.db"
    ledger = LedgerCaixa(db_path, clock=lambda: 100.0)
    _registrar(ledger)
    ledger.fechar()
    reaberto = LedgerCaixa(db_path, clock=lambda: 101.0)
    claim = reaberto.claim("worker-reaberto", lease_s=10)
    assert claim is not None
    assert claim["payload"]["decisao"] == "prosseguir"
    assert _contagens(db_path) == (1, 1)
    reaberto.fechar()


def test_crash_entre_ledger_e_outbox_recupera_rollback(tmp_path: Path) -> None:
    db_path = tmp_path / "caixa.db"
    processo = multiprocessing.get_context("spawn").Process(
        target=_crash_durante_outbox,
        args=(str(db_path),),
    )
    processo.start()
    processo.join(10)
    assert processo.exitcode == 23
    reaberto = LedgerCaixa(db_path)
    assert _contagens(db_path) == (0, 0)
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    reaberto.fechar()


def test_schema_legado_ou_desconhecido_falha_fechado(tmp_path: Path) -> None:
    legado = tmp_path / "legado.db"
    with sqlite3.connect(legado) as conn:
        conn.execute("CREATE TABLE caixa_ledger(decisao_id TEXT PRIMARY KEY)")
    with pytest.raises(RuntimeError, match="migração explícita"):
        LedgerCaixa(legado)
    futuro = tmp_path / "futuro.db"
    with sqlite3.connect(futuro) as conn:
        conn.execute("CREATE TABLE caixa_meta(singleton INTEGER, schema_version INTEGER)")
        conn.execute("INSERT INTO caixa_meta VALUES (1, 2)")
    with pytest.raises(RuntimeError, match="incompatível: 2"):
        LedgerCaixa(futuro)


def test_ledger_exige_arquivo_e_prazo_de_lease_finito(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="arquivo persistente"):
        LedgerCaixa(":memory:")
    ledger = LedgerCaixa(tmp_path / "caixa.db", clock=lambda: 1e308)
    _registrar(ledger)
    for lease_s in (1, 1e308, 10**10000):
        with pytest.raises(ValueError, match="lease|prazo"):
            ledger.claim("worker-a", lease_s=lease_s)
    with pytest.raises(ValueError, match="identificador de lease"):
        ledger.renovar_claim(2**63, "worker-a", lease_version=1, lease_s=1)
    assert _contagens(tmp_path / "caixa.db") == (1, 1)
    ledger.fechar()
