import time
import json
import sqlite3
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import motor.servico as servico_modulo
from motor.caixa import LedgerCaixa
from motor.modelos import ClienteStub
from motor.eventos import LogEventos
from motor.composicao_orcamento import RotaOrcadaCertificada
from motor.orcamento import ErroOrcamento, RepositorioOrcamento
from motor.servico import GerenciadorJobs as GerenciadorJobsProducao
from tests.helpers_grafo import (
    GerenciadorJobsTeste as GerenciadorJobs,
    dependencias_servico_stub,
)
from tests.test_grafo import SPEC, faz_roteador


def aguardar_estado(gerenciador: GerenciadorJobs, job_id: str, estado: str, timeout_s: float = 3):
    fim = time.time() + timeout_s
    ultimo = None
    while time.time() < fim:
        ultimo = gerenciador.status(job_id)
        if ultimo["estado"] == estado:
            return ultimo
        time.sleep(0.02)
    raise AssertionError(f"estado {estado!r} não alcançado; último={ultimo!r}")


@pytest.mark.parametrize("topologia", [
    None,
    (RotaOrcadaCertificada(
        "stub:unica", "stub-provider-unico", frozenset({"executor", "verifier"}),
    ),),
])
def test_servico_preflight_bloqueia_antes_de_registrar_job(tmp_path, topologia):
    cliente = ClienteStub(faz_roteador())
    deps = dependencias_servico_stub(cliente, tmp_path / "orcamento-preflight")
    deps["rotas_certificadas"] = topologia
    jobs = GerenciadorJobsProducao(
        db_path=tmp_path / "preflight.db", cliente=cliente, **deps,
    )
    try:
        with pytest.raises(ErroOrcamento, match="catalogo|dois providers"):
            jobs.iniciar(spec=SPEC, thread_id="preflight-bloqueado")
        assert jobs._jobs == {}
        assert jobs._threads == set()
    finally:
        jobs.fechar()


def test_servico_preflight_exige_teto_bootstrap_antes_de_registrar_job(tmp_path):
    cliente = ClienteStub(faz_roteador())
    deps = dependencias_servico_stub(cliente, tmp_path / "orcamento-sem-teto")
    deps["teto_bootstrap"] = None
    jobs = GerenciadorJobsProducao(
        db_path=tmp_path / "preflight-sem-teto.db", cliente=cliente, **deps,
    )
    try:
        with pytest.raises(ErroOrcamento, match="teto bootstrap"):
            jobs.iniciar(spec=SPEC, thread_id="preflight-sem-teto")
        assert jobs._jobs == {}
        assert jobs._threads == set()
    finally:
        jobs.fechar()


def test_servico_sem_topologia_bloqueia_resume_e_recovery_antes_de_estado(tmp_path):
    jobs = GerenciadorJobsProducao(
        db_path=tmp_path / "passivo.db",
        cliente=ClienteStub(faz_roteador()),
        repositorio_orcamento=RepositorioOrcamento(tmp_path / "orcamento-passivo"),
        fabrica_tentativas_orcadas=lambda *_args: [],
    )
    try:
        with pytest.raises(ErroOrcamento, match="catalogo"):
            jobs.responder_gate("job-passivo", "prosseguir")
        with pytest.raises(ErroOrcamento, match="catalogo"):
            jobs._recuperar_outbox("job-passivo")
        assert jobs._jobs == {}
        assert jobs._threads == set()
    finally:
        jobs.fechar()


def test_iniciar_retorna_imediato_e_chega_a_gate_pendente(tmp_path):
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
    )

    inicio = gerenciador.iniciar(missao_texto="pesquise oportunidades", thread_id="t1")

    assert inicio == {"job_id": "t1", "estado": "em_execucao"}
    status = aguardar_estado(gerenciador, "t1", "gate_pendente")
    assert status["gate"]["portao"] == "plano"
    assert {"pergunta", "opcoes"} <= set(status["gate"])


def test_servico_certificado_injeta_orcamento_e_identidade_estavel(tmp_path):
    cliente = ClienteStub(faz_roteador())
    deps = dependencias_servico_stub(cliente, tmp_path / "orcamento")
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor-orcado.db",
        workspace_base=tmp_path / "runs-orcadas",
        cliente=cliente,
        **deps,
    )
    try:
        gerenciador.iniciar(spec=SPEC, thread_id="servico-orcado")
        aguardar_estado(gerenciador, "servico-orcado", "gate_pendente")
        gerenciador.responder_gate("servico-orcado", "prosseguir")
        assert aguardar_estado(gerenciador, "servico-orcado", "concluido")["estado"] == "concluido"
        ledger = tmp_path / "orcamento" / "servico-orcado" / "orcamento.sqlite3"
        assert ledger.is_file()
        with sqlite3.connect(f"file:{ledger}?mode=ro", uri=True) as con:
            assert con.execute(
                "SELECT run_id,thread_id,teto,status FROM budget_session"
            ).fetchall() == [("servico-orcado", "servico-orcado", "2", "ACTIVE")]
            assert con.execute("SELECT COUNT(*) FROM budget_outbox").fetchone()[0] > 0
            assert con.execute(
                "SELECT DISTINCT estado FROM budget_outbox_claim"
            ).fetchall() == [("ACKED",)]
        eventos = [
            json.loads(linha)
            for linha in (tmp_path / "runs-orcadas" / "servico-orcado" / "log.jsonl")
            .read_text(encoding="utf-8").splitlines()
        ]
        assert {evento["evento"] for evento in eventos} >= {
            "custo.reservado", "custo.reconciliado",
        }
    finally:
        gerenciador.fechar()


def test_servico_rejeita_identidade_incompativel_com_ledger(tmp_path):
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor-id.db", cliente=ClienteStub(faz_roteador()),
    )
    try:
        with pytest.raises(ValueError, match="job_id inválido"):
            gerenciador.iniciar(spec=SPEC, thread_id="parte..parte")
    finally:
        gerenciador.fechar()


def test_servico_rejeita_cliente_sem_deps_antes_de_efeito(tmp_path):
    efeitos: list[str] = []
    cliente = ClienteStub(lambda papel, _prompt: efeitos.append(papel) or "INDEVIDO")
    with pytest.raises(ValueError, match="cliente injetado exige"):
        GerenciadorJobsProducao(
            db_path=tmp_path / "nao-criar.db", cliente=cliente,
        )
    assert efeitos == []
    assert not (tmp_path / "nao-criar.db").exists()


def test_falha_do_sink_monetario_recupera_so_apos_lease(tmp_path, monkeypatch):
    class LogFalho(LogEventos):
        def publicar_orcamento(self, *_args):
            raise RuntimeError("sink indisponivel")

    cliente = ClienteStub(faz_roteador())
    deps = dependencias_servico_stub(cliente, tmp_path / "orcamento-falho")
    log = LogFalho(tmp_path / "log-falho.jsonl")
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor-falho.db",
        workspace_base=tmp_path / "runs-falhos",
        cliente=cliente,
        log=log,
        **deps,
    )
    try:
        gerenciador.iniciar(spec=SPEC, thread_id="sink-falho")
        aguardar_estado(gerenciador, "sink-falho", "gate_pendente")
        gerenciador.responder_gate("sink-falho", "prosseguir")
        status = aguardar_estado(gerenciador, "sink-falho", "erro")
        assert status["erro"]["mensagem"] == "sink indisponivel"
        ledger = tmp_path / "orcamento-falho" / "sink-falho" / "orcamento.sqlite3"
        with sqlite3.connect(f"file:{ledger}?mode=ro", uri=True) as con:
            estados = {linha[0] for linha in con.execute(
                "SELECT estado FROM budget_outbox_claim"
            )}
        assert "ACKED" not in estados and estados <= {"PENDING", "CLAIMED"}
    finally:
        gerenciador.fechar()
        log.fechar()

    reiniciado = GerenciadorJobs(
        db_path=tmp_path / "motor-falho.db",
        workspace_base=tmp_path / "runs-falhos",
        cliente=cliente,
        **deps,
    )
    try:
        assert reiniciado.status("sink-falho") == {"estado": "em_execucao"}
        monkeypatch.setattr(servico_modulo.time, "time", lambda: 2**31)
        assert reiniciado.status("sink-falho")["estado"] == "concluido"
        with sqlite3.connect(f"file:{ledger}?mode=ro", uri=True) as con:
            assert con.execute(
                "SELECT DISTINCT estado FROM budget_outbox_claim"
            ).fetchall() == [("ACKED",)]
        eventos = [
            json.loads(linha)
            for linha in (tmp_path / "runs-falhos" / "sink-falho" / "log.jsonl")
            .read_text(encoding="utf-8").splitlines()
        ]
        assert any(evento["evento"] == "custo.reconciliado" for evento in eventos)
    finally:
        reiniciado.fechar()


def test_responder_gate_retoma_e_conclui(tmp_path):
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
    )
    gerenciador.iniciar(spec=SPEC, thread_id="t2")
    aguardar_estado(gerenciador, "t2", "gate_pendente")

    assert gerenciador.responder_gate("t2", "prosseguir") == {"estado": "em_execucao"}
    status = aguardar_estado(gerenciador, "t2", "concluido")

    assert status["resposta_final"] == "SÍNTESE FINAL DA MISSÃO"
    assert status["artefatos"] == []
    assert status["run"]["job_id"] == "t2"
    assert status["run"]["workspace"] == str(tmp_path / "runs" / "t2")
    assert status["run"]["log"] == "log.jsonl"


def test_status_reconstroi_gate_do_checkpoint_em_nova_instancia(tmp_path):
    db_path = tmp_path / "motor.db"
    gerenciador = GerenciadorJobs(
        db_path=db_path,
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
    )
    gerenciador.iniciar(spec=SPEC, thread_id="t3")
    aguardar_estado(gerenciador, "t3", "gate_pendente")

    novo = GerenciadorJobs(
        db_path=db_path,
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
    )
    status = novo.status("t3")

    assert status["estado"] == "gate_pendente"
    assert status["gate"]["portao"] == "plano"


def test_responder_gate_em_job_nao_pausado_vira_erro_tratavel(tmp_path):
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
    )

    status = gerenciador.responder_gate("inexistente", "prosseguir")

    assert status["estado"] == "erro"
    assert status["erro"]["tipo"] == "EstadoInvalido"


def test_falha_ao_abrir_log_encerra_job_com_erro(tmp_path, monkeypatch):
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
    )

    def falhar(_job_id: str, truncar: bool = True):
        raise ValueError("sequencia invalida na linha 9")

    monkeypatch.setattr(gerenciador, "_log_do_job", falhar)
    gerenciador.iniciar(spec=SPEC, thread_id="log-invalido")

    status = aguardar_estado(gerenciador, "log-invalido", "erro")
    assert status == {
        "estado": "erro",
        "erro": {
            "tipo": "ValueError",
            "mensagem": "sequencia invalida na linha 9",
        },
    }


def test_fan_out_dois_gates_aborta_e_log_reabre_com_seq_continua(tmp_path):
    runs = tmp_path / "runs"
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=runs,
        cliente=ClienteStub(faz_roteador(evaluator_aprova=False)),
    )
    gerenciador.iniciar(spec=SPEC, thread_id="fan-out-gates")
    plano = aguardar_estado(gerenciador, "fan-out-gates", "gate_pendente")
    assert plano["gate"]["portao"] == "plano"

    gerenciador.responder_gate("fan-out-gates", "prosseguir")
    cobertura = aguardar_estado(gerenciador, "fan-out-gates", "gate_pendente")
    assert cobertura["gate"]["portao"] == "cobertura"

    gerenciador.responder_gate("fan-out-gates", "abortar")
    abortado = aguardar_estado(gerenciador, "fan-out-gates", "erro")
    assert abortado["erro"]["tipo"] == "MissaoAbortada"
    gerenciador.fechar()

    path = runs / "fan-out-gates" / "log.jsonl"
    eventos = [json.loads(linha) for linha in path.read_text().splitlines()]
    assert [evento["seq"] for evento in eventos] == list(range(1, len(eventos) + 1))
    reaberto = LogEventos(path)
    reaberto.fechar()


@pytest.mark.parametrize("_repeticao", range(5))
def test_gate_so_fica_observavel_depois_que_writer_fecha(
    tmp_path, monkeypatch, _repeticao
):
    iniciou_fechamento = threading.Event()
    liberar_fechamento = threading.Event()
    fechar_real = LogEventos.fechar

    def fechar_bloqueado(log: LogEventos) -> None:
        iniciou_fechamento.set()
        assert liberar_fechamento.wait(timeout=3)
        fechar_real(log)

    interrupcao = SimpleNamespace(
        id="decisao-handoff",
        value={"portao": "plano", "pergunta": "Revisar?", "opcoes": "prosseguir"},
    )

    class GrafoControlado:
        def invoke(self, entrada, _config):
            if isinstance(entrada, dict):
                return {"__interrupt__": [interrupcao]}
            return {"resposta_final": "ok", "run_id": "handoff-writer", "resultados": []}

        def get_state(self, _config):
            return SimpleNamespace(interrupts=(interrupcao,), values={})

    monkeypatch.setattr(servico_modulo, "construir_grafo", lambda *_a, **_kw: GrafoControlado())
    monkeypatch.setattr(LogEventos, "fechar", fechar_bloqueado)
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
    )
    gerenciador.iniciar(spec=SPEC, thread_id="handoff-writer")

    assert iniciou_fechamento.wait(timeout=3)
    assert gerenciador.status("handoff-writer") == {"estado": "em_execucao"}
    liberar_fechamento.set()
    gate = aguardar_estado(gerenciador, "handoff-writer", "gate_pendente")
    assert gate["gate"]["portao"] == "plano"

    assert gerenciador.responder_gate("handoff-writer", "prosseguir") == {
        "estado": "em_execucao"
    }
    assert aguardar_estado(gerenciador, "handoff-writer", "concluido")[
        "estado"
    ] == "concluido"
    gerenciador.fechar()


def test_retomada_longa_renova_claim_sem_segundo_writer(tmp_path, monkeypatch):
    executor_iniciou = threading.Event()
    liberar_executor = threading.Event()

    def roteador(papel: str, prompt: str):
        if papel == "pesquisador":
            executor_iniciou.set()
            assert liberar_executor.wait(timeout=3)
        return faz_roteador()(papel, prompt)

    aberturas: list[str] = []
    abrir_real = GerenciadorJobs._log_do_job

    def contar_abertura(self, job_id: str, truncar: bool = True):
        if truncar:
            aberturas.append(job_id)
        return abrir_real(self, job_id, truncar)

    monkeypatch.setattr(GerenciadorJobs, "_log_do_job", contar_abertura)
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(roteador),
        outbox_poll_s=0.01,
        outbox_lease_s=0.15,
    )
    gerenciador.iniciar(spec=SPEC, thread_id="lease-longo")
    gate = aguardar_estado(gerenciador, "lease-longo", "gate_pendente")
    decision_id = gate["gate"]["decision_id"]
    gerenciador.responder_gate("lease-longo", "prosseguir")
    assert executor_iniciou.wait(timeout=3)

    observador = LedgerCaixa(tmp_path / "motor.db")
    limite = time.monotonic() + 3
    registro = observador.buscar_decisao(decision_id)
    while registro is not None and registro["lease_version"] < 2:
        assert time.monotonic() < limite
        time.sleep(0.01)
        registro = observador.buscar_decisao(decision_id)
    assert registro is not None and registro["estado"] == "CLAIMED"
    assert observador.claim(
        "consumer-concorrente", lease_s=1, decisao_id=decision_id
    ) is None
    assert aberturas.count("lease-longo") == 2
    assert gerenciador.status("lease-longo") == {"estado": "em_execucao"}

    liberar_executor.set()
    assert aguardar_estado(gerenciador, "lease-longo", "concluido")[
        "estado"
    ] == "concluido"
    assert aberturas.count("lease-longo") == 2
    observador.fechar()
    gerenciador.fechar()


def _spec_com_artefato() -> dict:
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {
            "id": "artefato-servico",
            "objetivo": "Gerar artefato",
            "contexto": "",
            "criterios_cobertura": ["artefato aprovado"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 10, "max_tentativas": 1},
        "subagentes": [{
            "id": "autor",
            "papel": "executor",
            "objetivo": "Gerar texto",
            "entradas": {},
            "resultado_esperado": "Texto final",
            "rubrica": ["tem texto"],
            "produz_artefatos": [{"nome": "saida.txt", "tipo": "txt"}],
        }],
        "gates": [],
        "sintese": {"instrucao": "Sintetize", "formato": "markdown"},
    }


def test_status_concluido_traz_refs_de_artefato_sem_blob(tmp_path):
    conteudo = "CONTEUDO PRIVADO DO ARTEFATO"

    def roteador(papel: str, prompt: str):
        if papel == "executor":
            return conteudo
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            return "FINAL SEM BLOB"
        raise AssertionError(f"papel inesperado: {papel}")

    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(roteador),
    )
    gerenciador.iniciar(spec=_spec_com_artefato(), thread_id="artefato")
    aguardar_estado(gerenciador, "artefato", "gate_pendente")
    gerenciador.responder_gate("artefato", "prosseguir")

    status = aguardar_estado(gerenciador, "artefato", "concluido")

    # O rodapé de cobertura de evidência entra depois do texto do sintetizador:
    # esta missão declara um artefato e nenhum portão de execução o cobre, então
    # a resposta diz isso. Comparar o texto cru voltaria a permitir entregar
    # artefato não provado com aparência de pronto.
    assert status["resposta_final"].startswith("FINAL SEM BLOB")
    assert "0 de 1 artefatos passaram por portão de execução" in status["resposta_final"]
    assert status["run"] == {
        "job_id": "artefato",
        "workspace": str(tmp_path / "runs" / "artefato"),
        "log": "log.jsonl",
    }
    assert status["artefatos"] == [{
        "nome": "saida.txt",
        "tipo": "txt",
        "caminho": str(tmp_path / "runs" / "artefato" / "artefatos" / "autor__saida.txt"),
        "subagente": "autor",
    }]
    caminho = Path(status["artefatos"][0]["caminho"])
    assert caminho.exists()
    assert caminho.read_text(encoding="utf-8") == conteudo
    assert conteudo not in json.dumps(status, ensure_ascii=False)


def test_resumo_em_gate_e_concluido_e_compacto(tmp_path):
    gerenciador = GerenciadorJobs(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(faz_roteador()),
    )
    gerenciador.iniciar(spec=SPEC, thread_id="resumo")
    aguardar_estado(gerenciador, "resumo", "gate_pendente")

    em_gate = gerenciador.resumo("resumo")

    assert em_gate["estado"] == "gate_pendente"
    assert em_gate["gate"] == {
        "portao": "plano",
        "pergunta": "Revise o plano. prosseguir / editar / abortar",
        "opcoes": "prosseguir · editar · abortar",
    }
    assert em_gate["progresso"] == "0/2 subagentes concluídos"
    assert any(m == "planner: spec com 2 subagentes" for m in em_gate["marcos"])
    assert "executor.chamado" not in json.dumps(em_gate, ensure_ascii=False)

    gerenciador.responder_gate("resumo", "prosseguir")
    aguardar_estado(gerenciador, "resumo", "concluido")
    concluido = gerenciador.resumo("resumo")

    assert concluido["estado"] == "concluido"
    assert concluido["gate"] is None
    assert concluido["resumo_resposta"] == "SÍNTESE FINAL DA MISSÃO"
    assert concluido["run"] == {
        "job_id": "resumo",
        "workspace": str(tmp_path / "runs" / "resumo"),
        "log": "log.jsonl",
    }
    assert "tarefa: concluída" in concluido["marcos"]
