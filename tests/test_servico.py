import time

from motor.modelos import ClienteStub
from motor.servico import GerenciadorJobs
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
