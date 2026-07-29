import multiprocessing
import json
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from operator import add
from pathlib import Path
from typing import Annotated, Any, cast

import pytest
import motor.servico as servico_modulo
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

from motor.caixa import CaixaFundador, LedgerCaixa, rodar_com_caixa
from motor.modelos import ClienteStub
from tests.audit_corpus import casos, executar_lote, materializar_corpus
from tests.helpers_grafo import GerenciadorJobsTeste as GerenciadorJobs
from tests.test_grafo import SPEC, faz_roteador


# `spawn` reimporta o pacote inteiro no filho; sob carga (varias suites em
# paralelo) isso passa facil de 10s e o join estourava dando `exitcode is None`,
# um vermelho que parece defeito e nao e. O orcamento aqui e generoso de
# proposito: quem corta travamento de verdade e o `timeout` do pytest.
_ESPERA_SPAWN_S = 60


def _esperar_saida(processo, esperado: int) -> None:
    processo.join(_ESPERA_SPAWN_S)
    assert processo.exitcode is not None, (
        f"processo spawn nao terminou em {_ESPERA_SPAWN_S}s (maquina sobrecarregada?)"
    )
    assert processo.exitcode == esperado



CASOS_H11 = casos("H11")


@pytest.fixture(scope="module")
def corpus_h11(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("corpus-h11"))


def test_manifest_h11_tem_cinco_casos() -> None:
    assert len(CASOS_H11) == 5


@pytest.fixture(scope="module")
def _lote_h11(corpus_h11) -> dict[str, str | None]:
    """Roda os casos deste dono num subprocesso só.

    Um subprocesso por caso pagava ~4,7s de arranque de interpretador para
    milissegundos de trabalho útil. A atribuição por caso continua: cada
    reprodutor abaixo lê o próprio veredito.
    """
    return executar_lote(corpus_h11, CASOS_H11)


@pytest.mark.parametrize("nodeid", CASOS_H11)
def test_reprodutor_h11(_lote_h11: dict[str, str | None], nodeid: str) -> None:
    assert _lote_h11[nodeid] is None, _lote_h11[nodeid]


class _Estado(TypedDict):
    decisoes: Annotated[list[str], add]


class _EstadoParalelo(TypedDict, total=False):
    decisoes: Annotated[list[str], add]
    spec: dict[str, Any]
    run_id: str


def _grafo(saver: SqliteSaver):
    def gate(_estado: _Estado) -> _Estado:
        decisao = interrupt({"portao": "gate", "opcoes": "prosseguir | abortar"})
        return {"decisoes": [f"gate:{decisao}"]}

    builder = StateGraph(_Estado)
    builder.add_node("gate", cast(Any, gate))
    builder.add_edge(START, "gate")
    builder.add_edge("gate", END)
    return builder.compile(checkpointer=saver)


def _grafo_paralelo(saver: SqliteSaver):
    def gate(nome: str):
        def executar(_estado: _EstadoParalelo) -> _EstadoParalelo:
            decisao = interrupt({"portao": nome, "opcoes": "sim | nao"})
            return {"decisoes": [f"{nome}:{decisao}"]}

        return executar

    builder = StateGraph(_EstadoParalelo)
    for nome in ("gate-a", "gate-b"):
        builder.add_node(nome, cast(Any, gate(nome)))
        builder.add_edge(START, nome)
        builder.add_edge(nome, END)
    return builder.compile(checkpointer=saver)


def _crash_consumer(db_path: str, checkpoint: str,
                    decisao_id: str, fronteira: str) -> None:
    ledger = LedgerCaixa(db_path)
    claim = ledger.claim("worker-crash", lease_s=0.2, decisao_id=decisao_id)
    assert claim is not None
    config = {"configurable": {"thread_id": "crash-h11"}}
    with SqliteSaver.from_conn_string(checkpoint) as saver:
        grafo = _grafo(saver)

        def fault(ponto: str) -> None:
            if ponto == fronteira:
                os._exit(71)

        ledger.consumir(
            claim,
            lambda payload: grafo.invoke(
                Command(resume={payload["decisao_id"]: payload["decisao"]}),
                config,
            ),
            fault=fault,
        )


def _preparar_crash(tmp_path: Path) -> tuple[Path, Path, str]:
    checkpoint = tmp_path / "checkpoint.sqlite"
    config = {"configurable": {"thread_id": "crash-h11"}}
    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
        inicial = _grafo(saver).invoke({"decisoes": []}, config)
    decisao_id = inicial["__interrupt__"][0].id
    db_path = tmp_path / "ledger.sqlite"
    ledger = LedgerCaixa(db_path)
    ledger.registrar_decisao(
        decisao_id=decisao_id, job_id="crash-h11",
        portao="gate", decisao="prosseguir",
    )
    ledger.fechar()
    return db_path, checkpoint, decisao_id


def _crash_servico(db_path: str, workspace: str) -> None:
    def fault(ponto: str) -> None:
        if ponto == "apos_claim":
            os._exit(72)

    jobs = GerenciadorJobs(
        db_path=db_path,
        workspace_base=workspace,
        cliente=ClienteStub(faz_roteador()),
        fault=fault,
        outbox_poll_s=0.01,
        outbox_lease_s=0.2,
    )
    jobs.iniciar(spec=SPEC, thread_id="restart-h11")
    fim = time.time() + 5
    while (status := jobs.status("restart-h11"))["estado"] == "em_execucao":
        assert time.time() < fim
        time.sleep(0.01)
    assert status["estado"] == "gate_pendente"
    jobs.responder_gate("restart-h11", "prosseguir")
    time.sleep(5)
    os._exit(73)


def test_ack_exige_owner_versao_e_lease_vivo(tmp_path: Path) -> None:
    agora = [100.0]
    ledger = LedgerCaixa(tmp_path / "ledger.sqlite", clock=lambda: agora[0])
    ledger.registrar_decisao(
        decisao_id="decisao-cas", job_id="job-cas",
        portao="gate", decisao="prosseguir",
    )
    claim = ledger.claim("worker-a", lease_s=10)
    assert claim is not None
    with pytest.raises(ValueError, match="transição"):
        ledger.ack(claim["outbox_id"], "worker-b", lease_version=1)
    agora[0] = 110.0
    with pytest.raises(ValueError, match="transição"):
        ledger.ack(claim["outbox_id"], "worker-a", lease_version=1)
    retomado = ledger.claim("worker-b", lease_s=10)
    assert retomado is not None
    assert ledger.ack(
        retomado["outbox_id"], "worker-b",
        lease_version=retomado["lease_version"],
    ) == "decisao-cas"
    ledger.fechar()


def test_runner_sem_thread_id_nao_reivindica_decisao_de_outro_job(
    tmp_path: Path,
) -> None:
    class GrafoInerte:
        def invoke(self, *_args: Any, **_kwargs: Any) -> dict:
            raise AssertionError("config inválida não pode executar o grafo")

        def get_state(self, *_args: Any, **_kwargs: Any) -> Any:
            raise AssertionError("config inválida não pode consultar o grafo")

    class LogInerte:
        def evento(self, *_args: Any, **_kwargs: Any) -> None:
            raise AssertionError("config inválida não pode emitir evento")

    ledger = LedgerCaixa(tmp_path / "ledger.sqlite", clock=lambda: 100.0)
    ledger.registrar_decisao(
        decisao_id="decisao-vitima", job_id="job-vitima",
        portao="gate", decisao="prosseguir",
    )
    caixa = CaixaFundador(tmp_path / "caixa", LogInerte())

    with pytest.raises(ValueError, match="thread_id"):
        rodar_com_caixa(GrafoInerte(), {}, {"configurable": {}}, caixa, caixa.log,
                        ledger=ledger)

    registro = ledger.buscar_decisao("decisao-vitima")
    assert registro is not None and registro["estado"] == "PENDING"
    ledger.fechar()


def test_servico_rejeita_job_id_que_o_ledger_nao_pode_persistir(
    tmp_path: Path,
) -> None:
    jobs = GerenciadorJobs(
        db_path=tmp_path / "motor.sqlite",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
    )
    with pytest.raises(ValueError, match="job_id"):
        jobs.iniciar(spec=SPEC, thread_id="j" * 129)
    jobs.fechar()


@pytest.mark.parametrize(
    ("poll_s", "lease_s"),
    [
        (0, 1), (float("nan"), 1), (1, -1), (1, True),
        pytest.param(10**10000, 1, id="poll-overflow"),
    ],
)
def test_config_outbox_invalida_falha_antes_de_criar_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    poll_s: float, lease_s: float,
) -> None:
    def thread_proibida(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("configuração inválida não pode criar worker")

    monkeypatch.setattr(threading, "Thread", thread_proibida)
    db_path = tmp_path / "motor.sqlite"
    with pytest.raises(ValueError, match="outbox_"):
        GerenciadorJobs(
            db_path=db_path,
            outbox_poll_s=poll_s,
            outbox_lease_s=lease_s,
        )
    assert not db_path.exists()


def test_fechar_nao_fecha_conexao_com_job_vivo_e_bloqueia_mutacoes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    jobs = GerenciadorJobs(
        db_path=tmp_path / "motor.sqlite",
        cliente=ClienteStub(faz_roteador()),
    )
    iniciou = threading.Event()
    liberar = threading.Event()

    def executar_bloqueado(*_args: Any, **_kwargs: Any) -> None:
        iniciou.set()
        assert liberar.wait(timeout=2)

    monkeypatch.setattr(jobs, "_executar", executar_bloqueado)
    jobs._iniciar_thread("job-vivo", cast(Any, object()), None)
    assert iniciou.wait(timeout=2)
    with pytest.raises(TimeoutError, match="workers"):
        jobs.fechar(timeout_s=0.01)
    assert jobs._conn.execute("SELECT 1").fetchone() == (1,)
    with pytest.raises(RuntimeError, match="fechado"):
        jobs.iniciar(spec=SPEC, thread_id="novo-job")
    with pytest.raises(RuntimeError, match="fechado"):
        jobs.responder_gate("job-vivo", "prosseguir")

    liberar.set()
    jobs.fechar()
    jobs.fechar()
    with pytest.raises(RuntimeError, match="fechado"):
        jobs.status("job-vivo")
    with pytest.raises(sqlite3.ProgrammingError):
        jobs._conn.execute("SELECT 1")


@pytest.mark.parametrize("fronteira", ["apos_claim", "apos_aplicar", "apos_ack"])
def test_crash_em_cada_fronteira_converge_apos_restart(
    tmp_path: Path, fronteira: str
) -> None:
    db_path, checkpoint, decisao_id = _preparar_crash(tmp_path)
    processo = multiprocessing.get_context("spawn").Process(
        target=_crash_consumer,
        args=(str(db_path), str(checkpoint), decisao_id, fronteira),
    )
    processo.start()
    _esperar_saida(processo, 71)

    ledger = LedgerCaixa(db_path)
    if fronteira != "apos_ack":
        time.sleep(0.25)
        claim = ledger.claim("worker-restart", lease_s=1, decisao_id=decisao_id)
        assert claim is not None
        config = {"configurable": {"thread_id": "crash-h11"}}
        with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
            grafo = _grafo(saver)
            ledger.consumir(
                claim,
                lambda payload: grafo.invoke(
                    Command(resume={payload["decisao_id"]: payload["decisao"]}),
                    config,
                ),
            )
    registro = ledger.buscar_decisao(decisao_id)
    assert registro is not None and registro["estado"] == "APPLIED"
    assert ledger.claim("worker-extra", lease_s=1, decisao_id=decisao_id) is None
    ledger.fechar()
    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
        assert _grafo(saver).get_state(
            {"configurable": {"thread_id": "crash-h11"}}
        ).values["decisoes"] == ["gate:prosseguir"]


def test_servico_reconcilia_automaticamente_apos_restart_de_processo(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "motor.sqlite"
    workspace = tmp_path / "runs"
    processo = multiprocessing.get_context("spawn").Process(
        target=_crash_servico,
        args=(str(db_path), str(workspace)),
    )
    processo.start()
    _esperar_saida(processo, 72)

    jobs = GerenciadorJobs(
        db_path=db_path,
        workspace_base=workspace,
        cliente=ClienteStub(faz_roteador()),
        outbox_poll_s=0.01,
        outbox_lease_s=1,
    )
    fim = time.time() + 5
    while True:
        with sqlite3.connect(db_path) as conn:
            linha = conn.execute(
                "SELECT decisao_id FROM caixa_ledger WHERE job_id = ?",
                ("restart-h11",),
            ).fetchone()
        registro = None
        if linha is not None:
            ledger = LedgerCaixa(db_path)
            registro = ledger.buscar_decisao(str(linha[0]))
            ledger.fechar()
        if registro is not None and registro["estado"] == "APPLIED":
            break
        assert time.time() < fim
        time.sleep(0.01)
    while (status := jobs.status("restart-h11"))["estado"] == "em_execucao":
        assert time.time() < fim
        time.sleep(0.01)
    assert status["estado"] == "concluido"
    ledger_orcamento = workspace / ".orcamento-teste" / "restart-h11" / "orcamento.sqlite3"
    assert ledger_orcamento.is_file()
    with sqlite3.connect(f"file:{ledger_orcamento}?mode=ro", uri=True) as con:
        assert con.execute(
            "SELECT run_id,thread_id,teto,status FROM budget_session"
        ).fetchall() == [("restart-h11", "restart-h11", "2", "ACTIVE")]
        assert con.execute("SELECT COUNT(*) FROM budget_outbox").fetchone()[0] > 0
        assert con.execute(
            "SELECT DISTINCT estado FROM budget_outbox_claim"
        ).fetchall() == [("ACKED",)]
    eventos = [
        json.loads(linha)
        for linha in (workspace / "restart-h11" / "log.jsonl")
        .read_text(encoding="utf-8").splitlines()
    ]
    assert any(evento["evento"] == "custo.reconciliado" for evento in eventos)
    jobs.fechar()


def test_claim_vivo_concede_um_unico_consumer(tmp_path: Path) -> None:
    db_path = tmp_path / "ledger.sqlite"
    efeitos = tmp_path / "efeitos.sqlite"
    base = LedgerCaixa(db_path)
    base.registrar_decisao(
        decisao_id="decisao-1", job_id="job-1",
        portao="gate", decisao="prosseguir",
    )
    base.fechar()
    with sqlite3.connect(efeitos) as conn:
        conn.execute("CREATE TABLE efeitos(valor TEXT NOT NULL)")
    barreira = threading.Barrier(2)

    def consumir(owner: str) -> bool:
        ledger = LedgerCaixa(db_path)
        barreira.wait(timeout=2)
        claim = ledger.claim(owner, lease_s=5, decisao_id="decisao-1")
        if claim is None:
            ledger.fechar()
            return False

        def aplicar(payload: dict) -> None:
            with sqlite3.connect(efeitos) as conn:
                conn.execute("INSERT INTO efeitos VALUES (?)", (payload["decisao"],))

        ledger.consumir(claim, aplicar)
        ledger.fechar()
        return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(consumir, ("worker-a", "worker-b"))) == 1
    with sqlite3.connect(efeitos) as conn:
        assert conn.execute("SELECT valor FROM efeitos").fetchall() == [("prosseguir",)]
    reaberto = LedgerCaixa(db_path)
    registro = reaberto.buscar_decisao("decisao-1")
    assert registro is not None and registro["estado"] == "APPLIED"
    reaberto.fechar()


def test_claim_serializa_mesmo_job_e_mantem_jobs_distintos_paralelos(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ledger.sqlite"
    base = LedgerCaixa(db_path)
    for decisao_id, job_id in (
        ("decisao-a1", "job-a"),
        ("decisao-a2", "job-a"),
        ("decisao-b1", "job-b"),
    ):
        base.registrar_decisao(
            decisao_id=decisao_id, job_id=job_id,
            portao="gate", decisao="sim",
        )
    outro = LedgerCaixa(db_path)
    claim_a1 = base.claim("worker-a", lease_s=10, decisao_id="decisao-a1")
    assert claim_a1 is not None
    assert outro.claim("worker-b", lease_s=10, decisao_id="decisao-a2") is None
    claim_b1 = outro.claim("worker-b", lease_s=10, decisao_id="decisao-b1")
    assert claim_b1 is not None
    registro_a2 = base.buscar_decisao("decisao-a2")
    assert registro_a2 is not None and registro_a2["estado"] == "PENDING"

    base.ack(
        claim_a1["outbox_id"], "worker-a",
        lease_version=claim_a1["lease_version"],
    )
    claim_a2 = outro.claim("worker-b", lease_s=10, decisao_id="decisao-a2")
    assert claim_a2 is not None
    outro.ack(
        claim_a2["outbox_id"], "worker-b",
        lease_version=claim_a2["lease_version"],
    )
    outro.ack(
        claim_b1["outbox_id"], "worker-b",
        lease_version=claim_b1["lease_version"],
    )
    base.fechar()
    outro.fechar()


def test_lease_expirado_redelivera_mas_efeito_deduplica_por_decision_id(
    tmp_path: Path,
) -> None:
    agora = [100.0]
    db_path = tmp_path / "ledger.sqlite"
    efeitos = tmp_path / "efeitos.sqlite"
    base = LedgerCaixa(db_path, clock=lambda: agora[0])
    base.registrar_decisao(
        decisao_id="decisao-redelivery", job_id="job-redelivery",
        portao="gate", decisao="prosseguir",
    )
    base.fechar()
    with sqlite3.connect(efeitos) as conn:
        conn.execute("CREATE TABLE efeitos(decisao_id TEXT PRIMARY KEY, decisao TEXT)")

    entrou_a = threading.Event()
    liberar_a = threading.Event()
    entregas: list[str] = []
    erros_a: list[Exception] = []

    def persistir(payload: dict[str, Any], worker: str) -> None:
        entregas.append(worker)
        with sqlite3.connect(efeitos) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO efeitos VALUES (?, ?)",
                (payload["decisao_id"], payload["decisao"]),
            )

    def consumir_a() -> None:
        ledger = LedgerCaixa(db_path, clock=lambda: agora[0])
        claim = ledger.claim("worker-a", lease_s=1)
        assert claim is not None

        def aplicar_a(payload: dict[str, Any]) -> None:
            entrou_a.set()
            assert liberar_a.wait(timeout=2)
            persistir(payload, "a")

        try:
            ledger.consumir(claim, aplicar_a)
        except ValueError as ex:
            erros_a.append(ex)
        finally:
            ledger.fechar()

    thread_a = threading.Thread(target=consumir_a)
    thread_a.start()
    assert entrou_a.wait(timeout=2)
    agora[0] = 102.0
    worker_b = LedgerCaixa(db_path, clock=lambda: agora[0])
    claim_b = worker_b.claim("worker-b", lease_s=10)
    assert claim_b is not None
    worker_b.consumir(claim_b, lambda payload: persistir(payload, "b"))
    liberar_a.set()
    thread_a.join(timeout=2)

    assert not thread_a.is_alive()
    assert entregas == ["b", "a"]
    assert len(erros_a) == 1 and "transição" in str(erros_a[0])
    with sqlite3.connect(efeitos) as conn:
        assert conn.execute("SELECT * FROM efeitos").fetchall() == [
            ("decisao-redelivery", "prosseguir")
        ]
    worker_b.fechar()


def test_consumer_rejeita_claim_mutado_antes_do_efeito(tmp_path: Path) -> None:
    ledger = LedgerCaixa(tmp_path / "ledger.sqlite")
    ledger.registrar_decisao(
        decisao_id="decisao-integra", job_id="job-integro",
        portao="gate", decisao="prosseguir",
    )
    claim = ledger.claim("worker-a", lease_s=10)
    assert claim is not None
    original = {**claim, "payload": dict(claim["payload"])}
    claim["payload"]["decisao"] = "forjada"
    efeitos: list[str] = []

    with pytest.raises(ValueError, match="diverge"):
        ledger.consumir(claim, lambda payload: efeitos.append(payload["decisao"]))

    assert efeitos == []
    ledger.consumir(original, lambda payload: efeitos.append(payload["decisao"]))
    assert efeitos == ["prosseguir"]
    ledger.fechar()


def test_lease_maximo_ainda_pode_ser_confirmado_sem_colidir_com_applied(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ledger.sqlite"
    ledger = LedgerCaixa(db_path)
    ledger.registrar_decisao(
        decisao_id="decisao-max", job_id="job-max",
        portao="gate", decisao="prosseguir",
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE caixa_outbox SET lease_version = ? WHERE decisao_id = ?",
            (2**63 - 2, "decisao-max"),
        )
    claim = ledger.claim("worker-max", lease_s=10)
    assert claim is not None and claim["lease_version"] == 2**63 - 1
    ledger.consumir(claim, lambda _payload: None)
    registro = ledger.buscar_decisao("decisao-max")
    assert registro is not None and registro["estado"] == "APPLIED"
    ledger.fechar()


def test_servico_real_concorrente_persiste_decision_id_e_ack(tmp_path: Path) -> None:
    db_path = tmp_path / "motor.sqlite"
    aplicacoes: list[str] = []
    lock_aplicacoes = threading.Lock()

    def fault(ponto: str) -> None:
        if ponto == "apos_aplicar":
            with lock_aplicacoes:
                aplicacoes.append(ponto)

    jobs_a = GerenciadorJobs(
        db_path=db_path, workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
        fault=fault, outbox_poll_s=0.01, outbox_lease_s=5,
    )
    jobs_a.iniciar(spec=SPEC, thread_id="servico-h11")
    fim = time.time() + 3
    while (status := jobs_a.status("servico-h11"))["estado"] == "em_execucao":
        assert time.time() < fim
        time.sleep(0.02)
    decisao_id = status["gate"]["decision_id"]
    jobs_b = GerenciadorJobs(
        db_path=db_path, workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
        fault=fault, outbox_poll_s=0.01, outbox_lease_s=5,
    )
    barreira = threading.Barrier(2)

    def responder(jobs: GerenciadorJobs) -> dict:
        barreira.wait(timeout=2)
        return jobs.responder_gate("servico-h11", "prosseguir")

    with ThreadPoolExecutor(max_workers=2) as pool:
        respostas = list(pool.map(responder, (jobs_a, jobs_b)))
    assert all(resposta["estado"] == "em_execucao" for resposta in respostas)
    fim = time.time() + 3
    while True:
        ledger = LedgerCaixa(db_path)
        registro = ledger.buscar_decisao(decisao_id)
        ledger.fechar()
        if registro is not None and registro["estado"] == "APPLIED":
            break
        assert time.time() < fim
        time.sleep(0.02)
    assert aplicacoes == ["apos_aplicar"]
    jobs_a.fechar()
    jobs_b.fechar()


def test_servico_serializa_dois_interrupts_paralelos_por_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def construir_paralelo(
        _cliente: Any, _log: Any, *, checkpointer: SqliteSaver, **_kwargs: Any,
    ) -> Any:
        return _grafo_paralelo(checkpointer)

    monkeypatch.setattr(servico_modulo, "construir_grafo", construir_paralelo)
    db_path = tmp_path / "motor.sqlite"
    primeira_aplicacao = threading.Event()
    liberar_primeira = threading.Event()
    aplicacoes: list[str] = []
    lock_aplicacoes = threading.Lock()
    fechamentos = 0
    lock_fechamentos = threading.Lock()
    fechar_real = servico_modulo.LogEventos.fechar

    def registrar_fechamento(log: Any) -> None:
        nonlocal fechamentos
        fechar_real(log)
        with lock_fechamentos:
            fechamentos += 1

    monkeypatch.setattr(servico_modulo.LogEventos, "fechar", registrar_fechamento)

    def fault(ponto: str) -> None:
        if ponto != "apos_aplicar":
            return
        with lock_fechamentos:
            assert fechamentos >= 2
        with lock_aplicacoes:
            aplicacoes.append(ponto)
            primeira = len(aplicacoes) == 1
        if primeira:
            primeira_aplicacao.set()
            assert liberar_primeira.wait(timeout=3)

    def novo_servico() -> GerenciadorJobs:
        return GerenciadorJobs(
            db_path=db_path,
            workspace_base=tmp_path / "runs",
            cliente=ClienteStub(faz_roteador()),
            fault=fault,
            outbox_poll_s=0.01,
            outbox_lease_s=5,
        )

    jobs_a = novo_servico()
    jobs_b = novo_servico()
    pool = ThreadPoolExecutor(max_workers=1)
    resposta_a = None
    try:
        jobs_a.iniciar(spec=SPEC, thread_id="paralelo-h11")
        fim = time.time() + 3
        while (status := jobs_a.status("paralelo-h11"))["estado"] == "em_execucao":
            assert time.time() < fim
            time.sleep(0.01)
        assert status["estado"] == "gate_pendente"
        assert len(status["gates"]) == 2
        assert status["gate"] == status["gates"][0]
        gates = {gate["portao"]: gate for gate in status["gates"]}
        id_a = gates["gate-a"]["decision_id"]
        id_b = gates["gate-b"]["decision_id"]

        ambigua = jobs_b.responder_gate("paralelo-h11", "sim")
        assert ambigua["erro"]["tipo"] == "DecisaoIdObrigatorio"
        with sqlite3.connect(db_path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM caixa_ledger").fetchone() == (0,)

        resposta_a = pool.submit(
            jobs_a.responder_gate, "paralelo-h11", "sim", id_a
        )
        assert primeira_aplicacao.wait(timeout=3)
        restantes = jobs_b._gates_duraveis("paralelo-h11")
        ids_restantes = {gate["decision_id"] for gate in restantes}
        assert id_b in ids_restantes
        assert ids_restantes <= {id_a, id_b}
        with jobs_b._lock:
            jobs_b._jobs["paralelo-h11"] = {"estado": "em_execucao"}
        assert jobs_b.responder_gate(
            "paralelo-h11", "nao", decision_id=id_b
        )["estado"] == "em_execucao"

        ledger = LedgerCaixa(db_path)
        registro_a = ledger.buscar_decisao(id_a)
        registro_b = ledger.buscar_decisao(id_b)
        ledger.fechar()
        assert registro_a is not None and registro_a["estado"] == "CLAIMED"
        assert registro_b is not None and registro_b["estado"] == "PENDING"

        liberar_primeira.set()
        assert resposta_a.result(timeout=3)["estado"] == "em_execucao"
        fim = time.time() + 5
        while True:
            ledger = LedgerCaixa(db_path)
            estados = [
                ledger.buscar_decisao(id_a), ledger.buscar_decisao(id_b),
            ]
            ledger.fechar()
            if all(item is not None and item["estado"] == "APPLIED" for item in estados):
                break
            assert time.time() < fim
            time.sleep(0.01)
        assert aplicacoes == ["apos_aplicar", "apos_aplicar"]
        with SqliteSaver.from_conn_string(str(db_path)) as saver:
            snapshot = _grafo_paralelo(saver).get_state(
                {"configurable": {"thread_id": "paralelo-h11"}}
            )
        assert sorted(snapshot.values["decisoes"]) == ["gate-a:sim", "gate-b:nao"]
        assert jobs_b.responder_gate(
            "paralelo-h11", "sim", decision_id=id_a
        )["estado"] == "em_execucao"
        divergente = jobs_b.responder_gate(
            "paralelo-h11", "nao", decision_id=id_a
        )
        assert divergente["erro"]["tipo"] == "EstadoInvalido"
    finally:
        liberar_primeira.set()
        pool.shutdown(wait=True, cancel_futures=True)
        jobs_a.fechar()
        jobs_b.fechar()
