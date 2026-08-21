"""Reproducoes de invariantes violados encontradas na auditoria Codex.

Estes testes sao deliberadamente vermelhos ate o hardening correspondente.
"""
from __future__ import annotations

import copy
import json
import sys
import threading
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from motor.curador import certificar_sombra, preparar_promocao_gated, rodar_sombra
from motor.eventos import LogEventos
from motor.eventos_schema import tipos, valido
from motor.grafo import construir_grafo
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates
from motor.servico import _validar_job_id
from tests.helpers_grafo import GerenciadorJobsTeste
from motor_painel.painel import parse_eventos


def _modelo() -> dict:
    return {
        "id": "executor",
        "tipo": "modelo",
        "papel": "executor",
        "objetivo": "produzir resultado",
        "entradas": {},
        "resultado_esperado": "texto",
        "rubrica": ["resultado correto"],
    }


def _spec(subagentes: list[dict], padrao: str = "fan_out_sintese") -> dict:
    return {
        "versao": "0.1",
        "padrao": padrao,
        "missao": {
            "id": "auditoria",
            "objetivo": "testar invariantes",
            "contexto": "",
            "criterios_cobertura": ["resultado aprovado"],
        },
        "restricoes": {
            "teto_custo": 1.0,
            "max_subagentes": len(subagentes),
            "max_tentativas": 1,
        },
        "subagentes": subagentes,
        "gates": [],
        "sintese": {"instrucao": "sintetize", "formato": "markdown"},
    }


def _ferramenta(entradas: dict | None = None) -> dict:
    return {
        "id": "tool",
        "tipo": "ferramenta",
        "ferramenta": "audit",
        "objetivo": "executar ferramenta",
        "entradas": entradas or {},
        "resultado_esperado": "exit code",
    }


def _rodar_grafo(tmp_path: Path, spec: dict, roteador, **kwargs):
    log = LogEventos(tmp_path / "eventos.jsonl")
    grafo = construir_grafo(
        ClienteStub(roteador),
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "prosseguir"}),
        workspace_base=tmp_path / "runs",
        **kwargs,
    )
    try:
        resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "audit"}})
    finally:
        log.fechar()
    eventos = [json.loads(linha) for linha in log.path.read_text(encoding="utf-8").splitlines()]
    return resultado, eventos


@pytest.mark.parametrize(
    "validador",
    [
        {"kind": "schema_json", "config": {}},
        {"kind": "contem", "config": {}},
        {"kind": "comando", "config": {"comando": ""}},
    ],
    ids=["schema-sem-schema", "contem-sem-requer", "comando-vazio"],
)
def test_s1_configuracao_invalida_falha_na_validacao_da_spec(validador):
    alvo = _modelo()
    no_validador = {
        "id": "validador",
        "tipo": "validador",
        "valida": "executor",
        "validador": validador,
        "depende_de": ["executor"],
        "objetivo": "validar",
        "resultado_esperado": "veredito",
    }

    from motor.spec import WorkflowSpec

    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(_spec([alvo, no_validador], "grafo_dependencias"))


def test_k3_verifier_exige_booleano_antes_de_aprovar(tmp_path):
    def roteador(papel, _prompt):
        respostas = {
            "executor": "rascunho",
            "verifier": json.dumps({"aprovado": "false", "motivo": "reprovado"}),
            "evaluator": json.dumps({"aprovado": True, "lacunas": []}),
            "synthesizer": "final",
        }
        return respostas[papel]

    resultado, _ = _rodar_grafo(tmp_path, _spec([_modelo()]), roteador)

    assert resultado["resultados"][0]["aprovado"] is False


def test_g4_excecao_do_executor_vira_resultado_e_evento_de_erro(tmp_path):
    def roteador(papel, _prompt):
        if papel == "executor":
            raise RuntimeError("falha injetada")
        return json.dumps({"aprovado": True, "lacunas": []})

    resultado, eventos = _rodar_grafo(tmp_path, _spec([_modelo()]), roteador)

    assert resultado["resultados"][0]["aprovado"] is False
    assert any(evento["evento"] == "executor.erro" for evento in eventos)


def test_c1_allowlist_nao_confunde_basename_com_executavel_autorizado(tmp_path):
    falso = tmp_path / "nao-confiavel" / "python3"
    falso.parent.mkdir()
    falso.write_text("#!/bin/sh\nprintf 'executou'\n", encoding="utf-8")
    falso.chmod(0o755)
    ferramentas = {"audit": {"comando": str(falso), "interpreta_saida": "exit_code"}}

    resultado, _ = _rodar_grafo(
        tmp_path,
        _spec([_ferramenta()]),
        lambda papel, _prompt: json.dumps({"aprovado": True, "lacunas": []})
        if papel == "evaluator"
        else "final",
        ferramentas=ferramentas,
        ferramentas_permitidas=["python3"],
    )

    assert resultado["resultados"][0]["aprovado"] is False


def test_c2_c4_validador_nao_escapa_workspace_por_placeholder(tmp_path):
    marcador = tmp_path / "fora-do-workspace.txt"
    validador = {
        "id": "validador",
        "tipo": "validador",
        "valida": "executor",
        "depende_de": ["executor"],
        "objetivo": "validar em sandbox",
        "resultado_esperado": "veredito",
        "entradas": {
            "modo": "-c",
            "codigo": f"from pathlib import Path; Path({str(marcador)!r}).write_text('executou')",
        },
        "validador": {
            "kind": "comando",
            "config": {"comando": f"{sys.executable} {{modo}} {{codigo}}"},
        },
    }

    _rodar_grafo(
        tmp_path,
        _spec([_modelo(), validador], "grafo_dependencias"),
        lambda papel, _prompt: (
            "saida"
            if papel == "executor"
            else "final"
            if papel == "synthesizer"
            else json.dumps({"aprovado": True, "lacunas": []})
        ),
        ferramentas_permitidas=[Path(sys.executable).name],
    )

    assert not marcador.exists()


def test_e1_todo_evento_emitido_pelo_curador_pertence_ao_schema():
    eventos = []

    def emitir(nome, _dados):
        eventos.append(nome)

    casos = [{"id": "1", "slot": "redator", "titular": {"aprovado": False, "custo_usd": 2.0}}]
    evidencia = rodar_sombra(
        {"slot": "redator", "titular": "atual", "candidato": "novo"},
        casos,
        lambda _caso, _modelo: {"aprovado": True, "custo_usd": 1.0},
        emitir,
    )
    certificacao = certificar_sombra(evidencia, emitir)
    preparar_promocao_gated(certificacao, emitir)

    assert set(eventos) <= tipos()


def test_e1_schema_rejeita_evento_sem_payload_obrigatorio():
    assert valido({"evento": "executor.chamado"}) is False


@pytest.mark.parametrize("campo", ["evento", "t", "seq", "event_id", "run_id"])
def test_e1_envelope_reserva_tipo_e_timestamp(tmp_path, campo):
    """O envelope é do log, não do chamador.

    A auditoria pedia que um payload forjado não sobrescrevesse `evento`/`t`.
    O hardening foi além: a chamada é RECUSADA em vez de silenciosamente
    corrigida — falha ruidosa vale mais que sobrescrita silenciosa, e o
    conjunto reservado cresceu para incluir `seq` e `event_id`.
    """
    log = LogEventos(tmp_path / "log.jsonl")
    try:
        with pytest.raises(ValueError, match="campo reservado"):
            log.evento("spec.recebida", **{campo: "forjado"})
        # e nada foi escrito
        assert log.path.read_text(encoding="utf-8") == ""
    finally:
        log.fechar()


def test_e2_reabrir_log_preserva_historico_por_padrao(tmp_path):
    """Reabrir um log v2 anexa, nunca trunca.

    Os payloads carregam os campos que o schema exige por tipo (`spec.recebida`
    → missao/subagentes; `tarefa.concluida` → missao). O invariante auditado
    (reabrir preserva histórico) segue valendo e é o que este teste prova.
    """
    caminho = tmp_path / "log.jsonl"
    primeiro = LogEventos(caminho)
    primeiro.evento("spec.recebida", missao="m", subagentes=1)
    primeiro.fechar()
    segundo = LogEventos(caminho)
    segundo.evento("tarefa.concluida", missao="m")
    segundo.fechar()

    linhas = [json.loads(linha) for linha in caminho.read_text().splitlines()]
    assert [e["evento"] for e in linhas] == ["spec.recebida", "tarefa.concluida"]
    # e a sequência continua contígua através da reabertura
    assert [e["seq"] for e in linhas] == [1, 2]


def test_e2_projecao_preserva_eventos_antes_de_tail_parcial(tmp_path):
    caminho = tmp_path / "log.jsonl"
    caminho.write_text('{"t": 0, "evento": "spec.recebida"}\n{"t":', encoding="utf-8")

    assert parse_eventos(caminho) == [{"t": 0, "evento": "spec.recebida"}]


def test_u1_runner_nao_pode_mutar_casos_held_out():
    casos = [{
        "id": "1",
        "slot": "redator",
        "entrada": {"texto": "original"},
        "titular": {"aprovado": True, "custo_usd": 2.0},
    }]
    original = copy.deepcopy(casos)

    def runner(caso, _modelo):
        caso["entrada"]["texto"] = "alterado"
        caso["titular"]["aprovado"] = False
        return {"aprovado": True, "custo_usd": 1.0}

    rodar_sombra({"slot": "redator", "titular": "atual", "candidato": "novo"}, casos, runner)

    assert casos == original


def test_u2_custo_parcial_do_candidato_e_incomparavel():
    casos = [
        {"id": "1", "slot": "redator", "titular": {"aprovado": True, "custo_usd": 0.02}},
        {"id": "2", "slot": "redator", "titular": {"aprovado": False, "custo_usd": 0.02}},
    ]
    resultados = iter([
        {"aprovado": True, "custo_usd": 0.01},
        {"aprovado": True, "custo_usd": None},
    ])
    evidencia = rodar_sombra(
        {"slot": "redator", "titular": "atual", "candidato": "novo"},
        casos,
        lambda _caso, _modelo: next(resultados),
    )

    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_u2_aprovado_exige_booleano_estrito():
    casos = [{"id": "1", "slot": "redator", "titular": {"aprovado": False, "custo_usd": 0.02}}]
    evidencia = rodar_sombra(
        {"slot": "redator", "titular": "atual", "candidato": "novo"},
        casos,
        lambda _caso, _modelo: {"aprovado": "false", "custo_usd": 0.01},
    )

    assert evidencia["candidato"]["aprovados"] == 0
    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_u2_certificacao_rejeita_agregados_sem_casos_e_proveniencia():
    evidencia = {
        "status": "nao_e_sombra",
        "slot": "redator",
        "casos": [],
        "titular": {"modelo": "atual", "taxa_aprovacao": 0.0, "custo_medio_usd": 2.0},
        "candidato": {"modelo": "novo", "taxa_aprovacao": 1.0, "custo_medio_usd": 1.0},
    }

    assert certificar_sombra(evidencia)["status"] == "rejeitado"


def test_u3_status_certificado_sem_evidencia_nao_gera_intencao():
    assert preparar_promocao_gated({"status": "certificado"})["status"] == "promocao_vetada"


@pytest.mark.parametrize("gate", ["promocao", "autorizacao", "risco", "dinheiro"])
def test_f3_auto_mode_nao_responde_gate_sensivel(gate):
    """Gate sensível nunca é respondido sozinho, nem com auto_mode ligado."""
    assert PoliticaGates(auto_mode=True).decisao_auto(gate) is None


@pytest.mark.parametrize("gate", ["plano", "cobertura"])
def test_f3_gate_de_fluxo_e_automatizavel_mas_nunca_por_default(gate):
    """`plano`/`cobertura` decidem PAUSA, não autoridade — e o default é manual.

    A auditoria assumiu que todo gate deveria ser manual. A fronteira real é
    outra: gate sensível (promocao/autorizacao/risco/dinheiro) trata de
    permissão, risco e dinheiro e é sempre manual; gate de fluxo só decide se o
    motor te acorda. Mesmo assim, o default é manual — `auto_mode` é opt-in
    explícito — e a decisão automática nunca significa "aprovado": o avaliador de
    cobertura continua rodando e é ele que atesta qualidade.

    ATUALIZADO 2026-07-29: o automático de `cobertura` passou de "prosseguir"
    para "escalar". "prosseguir" liberava o portão REPROVADO e foi assim que uma
    missão vermelha saiu apresentada como entregue. `plano` segue "prosseguir"
    porque ele decide seguir com um plano, não declarar trabalho pronto.
    """
    esperado = {"plano": "prosseguir", "cobertura": "escalar"}[gate]
    assert PoliticaGates().decisao_auto(gate) is None, "default tem que ser manual"
    assert PoliticaGates(auto_mode=True).decisao_auto(gate) == esperado
    # e o operador pode recravar manual mesmo com auto_mode ligado
    politica = PoliticaGates(auto_mode=True, overrides={gate: "manual"})
    assert politica.decisao_auto(gate) is None


def test_f3_auto_mode_nunca_aborta_missao():
    """auto = "não me interrompa", jamais "mate a missão"."""
    politica = PoliticaGates(auto_mode=True)
    for gate in ("plano", "cobertura"):
        assert politica.decisao_auto(gate) != "abortar"


def test_job_id_nao_aceita_segmentos_de_traversal():
    with pytest.raises(ValueError):
        _validar_job_id("..")


def test_resposta_concorrente_ao_gate_so_dispara_um_resume(tmp_path, monkeypatch):
    # GerenciadorJobsTeste: o serviço produtivo agora exige deps de orçamento
    # explícitas (topologia certificada + teto). O helper fornece as fakes sem
    # afrouxar o construtor real, que segue fail-closed.
    jobs = GerenciadorJobsTeste(
        db_path=tmp_path / "motor.db",
        workspace_base=tmp_path / "runs",
        cliente=ClienteStub(lambda *_: None),
    )
    barreira = threading.Barrier(2)
    inicios = []
    respostas = []

    def status(_job_id):
        barreira.wait()
        return {"estado": "gate_pendente"}

    monkeypatch.setattr(jobs, "status", status)
    monkeypatch.setattr(jobs, "_iniciar_thread", lambda *args: inicios.append(args))
    threads = [threading.Thread(target=lambda: respostas.append(jobs.responder_gate("job", "prosseguir"))) for _ in range(2)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        jobs._conn.close()

    assert len(inicios) == 1
    assert sum(resposta["estado"] == "em_execucao" for resposta in respostas) == 1
