import json
from decimal import Decimal
from pathlib import Path

import motor.grafo as modulo_grafo
from motor.eventos import LogEventos
from motor.eventos_schema import valido
from motor.grafo import construir_grafo
from motor.modelos import ClienteStub
from motor.orcamento import (
    ResultadoTentativa,
    RepositorioOrcamento,
    RotaTentativaCusteada,
    TentativaBloqueadaPreEfeito,
    TentativaReconciliada,
    TentativaTerminal,
)
from motor.politica import PoliticaGates
from tests.helpers_grafo import TETO_OPERADOR_TESTE


SPEC = json.loads(
    (Path(__file__).parent.parent / "exemplos" / "missao-pesquisa.json").read_text()
)


def _spec_minima() -> dict:
    spec = json.loads(json.dumps(SPEC))
    spec["subagentes"] = [spec["subagentes"][0]]
    spec["restricoes"]["max_tentativas"] = 1
    spec["restricoes"]["max_rodadas_reconciliacao"] = 0
    return spec


def _eventos(tmp_path, monkeypatch, fabrica, executar):
    caminho = tmp_path / "eventos.jsonl"
    log = LogEventos(caminho)
    monkeypatch.setattr(modulo_grafo, "executar_tentativa_custeada", executar)
    grafo = construir_grafo(
        ClienteStub(lambda *_: "cliente legado nao pode ser chamado"),
        log,
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        repositorio_orcamento=RepositorioOrcamento(tmp_path / "orcamento"),
        fabrica_tentativas_orcadas=fabrica,
        teto_bootstrap=TETO_OPERADOR_TESTE,
    )
    try:
        grafo.invoke({"spec": _spec_minima(), "run_id": "run-diagnostico", "thread_id": "thread"})
    finally:
        log.fechar()
    eventos = [json.loads(linha) for linha in caminho.read_text().splitlines()]
    assert all(valido(evento) for evento in eventos)
    return eventos


def _sucesso(texto: str) -> TentativaReconciliada:
    return TentativaReconciliada(
        ResultadoTentativa(texto, Decimal("0"), "BRL", "usage-diagnostico")
    )


def test_rota_falha_emite_modelo_falha_com_classe_e_coordenada(tmp_path, monkeypatch):
    def fabrica(papel, *_):
        if papel == "pesquisador":
            return [
                RotaTentativaCusteada("rota-a", "provedor-a", object()),
                RotaTentativaCusteada("rota-b", "provedor-b", object()),
            ]
        return [RotaTentativaCusteada(f"rota-{papel}", f"provedor-{papel}", object())]

    def executar(_repo, _sessao, identidade, _adaptador):
        if identidade.route_id == "rota-a":
            return TentativaBloqueadaPreEfeito("sem_cotacao")
        if identidade.route_id == "rota-b":
            return _sucesso("rascunho")
        if identidade.route_id == "rota-verifier":
            return _sucesso(json.dumps({"aprovado": True, "motivo": "ok"}))
        if identidade.route_id == "rota-evaluator":
            return _sucesso(json.dumps({"aprovado": True, "lacunas": []}))
        return _sucesso("síntese")

    eventos = _eventos(tmp_path, monkeypatch, fabrica, executar)

    falhas = [evento for evento in eventos if evento["evento"] == "modelo.falha"]
    assert [evento["rota"] for evento in falhas] == ["rota-a"]
    assert falhas[0]["papel"] == "pesquisador"
    assert falhas[0]["provedor"] == "provedor-a"
    assert falhas[0]["fase"] == "executor"
    assert falhas[0]["classe"] == "pre_efeito"
    assert falhas[0]["motivo"] == "sem_cotacao"


def test_executor_erro_carrega_classe_pre_efeito_da_cadeia(tmp_path, monkeypatch):
    def fabrica(papel, *_):
        if papel == "pesquisador":
            return [
                RotaTentativaCusteada("rota-a", "provedor-a", object()),
                RotaTentativaCusteada("rota-b", "provedor-b", object()),
            ]
        return [RotaTentativaCusteada(f"rota-{papel}", f"provedor-{papel}", object())]

    def executar(_repo, _sessao, identidade, _adaptador):
        if identidade.route_id.startswith("rota-") and identidade.route_id in {"rota-a", "rota-b"}:
            return TentativaBloqueadaPreEfeito("teto")
        if identidade.route_id == "rota-verifier":
            return _sucesso(json.dumps({"aprovado": True, "motivo": "ok"}))
        if identidade.route_id == "rota-evaluator":
            return _sucesso(json.dumps({"aprovado": True, "lacunas": []}))
        return _sucesso("síntese")

    eventos = _eventos(tmp_path, monkeypatch, fabrica, executar)
    erros = [
        evento for evento in eventos
        if evento["evento"] == "executor.erro" and evento["executor"] == "pesquisa-alfa"
    ]
    assert len(erros) == 1
    assert erros[0]["classe"] == "pre_efeito"
    assert erros[0]["papel"] == "pesquisador"
    assert "rota-a=teto" in erros[0]["motivo"]


def test_falha_do_verifier_fica_em_modelo_falha_com_fase_verifier(tmp_path, monkeypatch):
    def fabrica(papel, *_):
        return [RotaTentativaCusteada(f"rota-{papel}", f"provedor-{papel}", object())]

    def executar(_repo, _sessao, identidade, _adaptador):
        if identidade.route_id == "rota-executor":
            return _sucesso("rascunho")
        if identidade.route_id == "rota-verifier":
            return TentativaTerminal("efeito externo com custo desconhecido", "UNKNOWN_COST")
        if identidade.route_id == "rota-evaluator":
            return _sucesso(json.dumps({"aprovado": True, "lacunas": []}))
        return _sucesso("síntese")

    eventos = _eventos(tmp_path, monkeypatch, fabrica, executar)
    falhas_verifier = [
        evento for evento in eventos
        if evento["evento"] == "modelo.falha" and evento.get("fase") == "verifier"
    ]
    assert len(falhas_verifier) == 1
    assert falhas_verifier[0]["rota"] == "rota-verifier"
    assert falhas_verifier[0]["classe"] == "terminal"
    assert "efeito externo com custo desconhecido" in falhas_verifier[0]["motivo"]
    assert not any(
        evento["evento"] == "executor.erro"
        and evento.get("executor") == "pesquisa-alfa"
        and "efeito externo com custo desconhecido" in evento.get("motivo", "")
        for evento in eventos
    )


def test_sem_rota_emite_registro_proprio_e_nao_finge_veredito_invalido(tmp_path, monkeypatch):
    def fabrica(papel, *_):
        if papel == "verifier":
            return []
        return [RotaTentativaCusteada(f"rota-{papel}", f"provedor-{papel}", object())]

    def executar(_repo, _sessao, identidade, _adaptador):
        if identidade.route_id == "rota-executor":
            return _sucesso("rascunho")
        if identidade.route_id == "rota-evaluator":
            return _sucesso(json.dumps({"aprovado": True, "lacunas": []}))
        return _sucesso("síntese")

    eventos = _eventos(tmp_path, monkeypatch, fabrica, executar)
    sem_rota = [
        evento for evento in eventos
        if evento["evento"] == "registro.sem_executor" and evento.get("classe") == "sem_rota"
    ]
    assert len(sem_rota) == 1
    assert sem_rota[0]["papel"] == "verifier"
    assert sem_rota[0]["fase"] == "verifier"
    assert sem_rota[0]["motivo"] == "nenhuma rota elegível"
    assert all(
        not (
            evento["evento"] == "executor.erro"
            and evento.get("executor") == "pesquisa-alfa"
            and evento.get("papel") == "verifier"
        )
        for evento in eventos
    )
    assert all(
        evento.get("motivo") != "verifier sem veredito valido"
        for evento in eventos if evento["evento"] == "executor.erro"
    )
