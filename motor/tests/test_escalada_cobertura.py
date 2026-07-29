"""Escalada do portão de cobertura: portão reprovado nunca passa reto.

Contrato decidido pelo Caio em 2026-07-29, depois de um run real em que
`--auto` liberou cobertura REPROVADA e a missão saiu apresentada como entregue:

- automático total  → sobe para um juiz INDEPENDENTE fazer o papel do fundador;
- teto de escaladas → esgotou, CHAMA o fundador (degrada para humano);
- sem juiz independente → também chama; falta de segunda opinião não é aprovação;
- `prosseguir` cego → continua existindo, mas só como override explícito.

O invariante que amarra tudo: **nenhum caminho automático libera cobertura
reprovada em silêncio**. Ele pode aprovar com prova, reconciliar, ou parar.
"""
from __future__ import annotations

import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.modelos import ClienteStub
from motor.orcamento import RequisitosTentativaCusteada, RotaTentativaCusteada
from motor.politica import PoliticaGates
from tests.helpers_grafo import dependencias_stub

SPEC = {
    "versao": "0.1",
    "padrao": "fan_out_sintese",
    "missao": {"id": "escalada", "objetivo": "o", "contexto": "",
               "criterios_cobertura": ["c"]},
    "restricoes": {"teto_custo": 1.0, "max_subagentes": 1, "max_tentativas": 1},
    "subagentes": [{"id": "alfa", "papel": "executor", "objetivo": "produzir",
                    "entradas": {}, "resultado_esperado": "texto",
                    "rubrica": ["ok"]}],
    "gates": [],
    "sintese": {"instrucao": "s", "formato": "markdown"},
}


def _deps_multi_provedor(cliente, tmp_path, provedores=("anthropic", "openai")):
    """Cadeia com mais de um provedor por papel — sem isso não existe escalada.

    Reusa a fábrica stub e apenas amplia a cadeia, para que `evitar_provedor`
    tenha de fato para onde ir.
    """
    base = dependencias_stub(cliente, tmp_path)
    fabrica_original = base["fabrica_tentativas_orcadas"]

    def fabricar(papel, prompt, tentativa, requisitos):
        rotas = []
        for provider in provedores:
            if requisitos.evitar_provedor == provider:
                continue
            origem = fabrica_original(
                papel, prompt, tentativa,
                RequisitosTentativaCusteada(ferramentas=requisitos.ferramentas),
            )
            if not origem:
                continue
            rotas.append(RotaTentativaCusteada(
                f"{origem[0].route_id}:{provider}", provider, origem[0].adaptador,
            ))
        return rotas

    return {**base, "fabrica_tentativas_orcadas": fabricar}


def _rodar(tmp_path, roteador, *, provedores=("anthropic", "openai"), **over):
    log = LogEventos(tmp_path / "log.jsonl")
    cliente = ClienteStub(roteador)
    deps = _deps_multi_provedor(cliente, tmp_path, provedores)
    grafo = construir_grafo(
        cliente, log, checkpointer=InMemorySaver(),
        politica=PoliticaGates(auto_mode=True),
        workspace_base=tmp_path / "runs",
        **deps, **over,
    )
    try:
        res = grafo.invoke({"spec": SPEC}, {"configurable": {"thread_id": "esc"}})
    finally:
        log.fechar()
    eventos = [json.loads(x) for x in (tmp_path / "log.jsonl").read_text().splitlines()]
    return res, [e["evento"] for e in eventos], eventos


def _roteador(vereditos):
    """`vereditos` é a fila de respostas do evaluator, na ordem das chamadas."""
    chamadas = {"evaluator": 0}

    def roteador(papel, _prompt):
        if papel == "evaluator":
            i = min(chamadas["evaluator"], len(vereditos) - 1)
            chamadas["evaluator"] += 1
            return json.dumps(vereditos[i])
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "synthesizer":
            return "FINAL"
        return "RESULTADO"

    return roteador


# --------------------------------------------------------------------------

def test_juiz_independente_aprova_e_o_portao_passa_sem_carimbo(tmp_path) -> None:
    """Escalada que APROVA é aprovação de verdade: sem `prosseguir_parcial`,
    logo sem carimbo. Foi provado por um segundo julgamento, não liberado."""
    res, tipos, _ = _rodar(tmp_path, _roteador([
        {"aprovado": False, "lacunas": ["falta evidência"], "nos_a_refazer": []},
        {"aprovado": True, "lacunas": []},
    ]))
    assert "gate.escalado" in tipos
    assert "__interrupt__" not in res
    assert res["avaliacao"]["aprovado"] is True
    assert not res["avaliacao"].get("prosseguir_parcial")
    assert not res["resposta_final"].startswith("⚠️")


def test_escalada_evita_o_provedor_que_ja_julgou(tmp_path) -> None:
    """O ponto inteiro da escalada.

    Pedir de novo ao mesmo provedor é pedir a mesma opinião mais alto — dois
    vereditos correlacionados têm aparência de revisão sem serem revisão.
    """
    _res, _tipos, eventos = _rodar(tmp_path, _roteador([
        {"aprovado": False, "lacunas": ["x"], "nos_a_refazer": []},
        {"aprovado": True, "lacunas": []},
    ]))
    escalado = [e for e in eventos if e["evento"] == "gate.escalado"]
    assert escalado and escalado[0]["evitando"] == "anthropic"


def test_sem_juiz_independente_chama_o_fundador_em_vez_de_liberar(tmp_path) -> None:
    """Um provedor só: a escalada é impossível. O portão NÃO relaxa por isso."""
    res, tipos, _ = _rodar(tmp_path, _roteador([
        {"aprovado": False, "lacunas": ["x"], "nos_a_refazer": []},
    ]), provedores=("anthropic",))
    assert "escalada.indisponivel" in tipos
    assert "__interrupt__" in res
    assert res["__interrupt__"][0].value["portao"] == "cobertura"


def test_teto_de_escaladas_degrada_para_humano(tmp_path) -> None:
    """A contenção principal do modo automático.

    Escalada é o primeiro lugar do sistema onde uma falha gera trabalho sozinha;
    sem teto, um portão teimoso consome a assinatura a noite inteira. Esgotado, o
    motor chama o fundador — degrada para humano, nunca para liberação.
    """
    res, tipos, _ = _rodar(
        tmp_path,
        _roteador([{"aprovado": False, "lacunas": ["x"], "nos_a_refazer": []}]),
        max_escaladas=0,
    )
    assert "escalada.esgotada" in tipos
    assert "gate.escalado" not in tipos
    assert "__interrupt__" in res


def test_escalada_que_reprova_de_novo_reconcilia_antes_de_chamar(tmp_path) -> None:
    """Com nó a refazer, o juiz independente manda reconciliar — é o que o
    fundador faria. Chamar humano é o último recurso, não o primeiro."""
    res, tipos, _ = _rodar(tmp_path, _roteador([
        {"aprovado": False, "lacunas": ["x"], "nos_a_refazer": ["alfa"]},
        {"aprovado": False, "lacunas": ["x"], "nos_a_refazer": ["alfa"]},
        {"aprovado": True, "lacunas": []},
    ]), max_rodadas_reconciliacao=2)
    assert "gate.escalado" in tipos
    assert "preenchimento.iniciado" in tipos or res["avaliacao"].get("aprovado")


@pytest.mark.parametrize("veredito_final", [
    {"aprovado": False, "lacunas": ["x"], "nos_a_refazer": []},
])
def test_nenhum_caminho_automatico_libera_cobertura_reprovada_calado(
    tmp_path, veredito_final
) -> None:
    """O invariante que amarra o contrato inteiro.

    Sob `auto_mode`, com a cobertura reprovando sempre, o motor pode fazer três
    coisas: aprovar com prova, reconciliar, ou parar. O que ele NÃO pode é
    terminar sozinho com resposta final sem carimbo — que é exatamente o que
    aconteceu no run de 2026-07-28.
    """
    res, _tipos, _ = _rodar(tmp_path, _roteador([veredito_final]))
    parou = "__interrupt__" in res
    carimbado = str(res.get("resposta_final", "")).startswith("⚠️ RUN REPROVADO")
    assert parou or carimbado, "cobertura reprovada saiu limpa e sem pausa"
