import time
import json
from pathlib import Path

import pytest

import motor.servico as servico_modulo
from motor.modelos import ClienteStub
from motor.servico import GerenciadorJobs
from tests.helpers_grafo import construir_grafo_teste
from tests.test_grafo import SPEC, faz_roteador


@pytest.fixture(autouse=True)
def _grafo_servico_offline(monkeypatch):
    monkeypatch.setattr(servico_modulo, "construir_grafo", construir_grafo_teste)


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

    assert status["resposta_final"] == "FINAL SEM BLOB"
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
