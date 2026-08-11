"""Spec que não declara `teto_custo` herda o teto do operador.

Descoberto rodando: `Restricoes.teto_custo` tem default 2.0 no schema e é o teto
real de gasto de todo nó custeado. O planner nunca declarou nada — o orçamento
efetivo da missão era um default de Pydantic, não os R$ que o operador
autorizou. Herdar mantém o bootstrap como única autoridade monetária.
"""
from __future__ import annotations

import json
from decimal import Decimal

from motor.eventos import LogEventos
from motor.modelos import ClienteStub
from motor.spec import WorkflowSpec

from tests.helpers_grafo import construir_grafo_teste


def _roteador(papel: str, _prompt: str) -> str:
    if papel == "verifier":
        return json.dumps({"aprovado": True, "motivo": "ok"})
    if papel == "evaluator":
        return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
    if papel == "synthesizer":
        return "FINAL"
    return "texto"


def _bruto(com_teto: bool) -> dict:
    restricoes: dict = {"max_subagentes": 3, "max_tentativas": 1}
    if com_teto:
        restricoes["teto_custo"] = 1.5
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {"id": "m", "objetivo": "o", "contexto": "c",
                   "criterios_cobertura": ["entrega algo"]},
        "restricoes": restricoes,
        "subagentes": [{"id": "a", "tipo": "modelo", "papel": "executor",
                        "objetivo": "x", "entradas": {}, "tier": "simples",
                        "resultado_esperado": "texto",
                        "rubrica": ["entrega texto"],
                        "capacidades_requeridas": ["redacao"]}],
        "sintese": {"instrucao": "i", "formato": "markdown"},
    }


def _rodar(tmp_path, spec: dict, thread: str) -> dict:
    log = LogEventos(tmp_path / f"{thread}.jsonl")
    grafo = construir_grafo_teste(ClienteStub(_roteador), log, teto_bootstrap=Decimal("80"))
    return grafo.invoke({"spec": spec}, {"configurable": {"thread_id": thread}})


def test_default_do_schema_e_2_reais(tmp_path) -> None:
    """Fixa a premissa: sem a herança, é este 2.0 que vira o orçamento."""
    assert WorkflowSpec.model_validate(_bruto(False)).restricoes.teto_custo == 2.0


def test_spec_sem_teto_custo_herda_o_do_operador(tmp_path) -> None:
    resultado = _rodar(tmp_path, _bruto(False), "herda")
    assert resultado["spec"]["restricoes"]["teto_custo"] == 80.0


def test_spec_que_declara_teto_mantem_o_declarado(tmp_path) -> None:
    """Declarar é apertar deliberadamente; o motor não desfaz isso."""
    resultado = _rodar(tmp_path, _bruto(True), "declara")
    assert resultado["spec"]["restricoes"]["teto_custo"] == 1.5


def test_spec_gerada_pelo_planner_sempre_herda(tmp_path) -> None:
    """Mesmo declarando: o planner recebe o schema no prompt e ecoa o default.

    Foi o que aconteceu na run 02 — `teto_custo: 2.0` escrito pelo planner, e o
    evaluator morreu em `custo.bloqueado` com teto 2 sobre R$ 0,81 já gastos.
    """
    bruto = _bruto(True)  # o planner ATÉ declara — e mesmo assim é eco

    def roteador(papel: str, prompt: str) -> str:
        if papel == "planner":
            return json.dumps(bruto)
        return _roteador(papel, prompt)

    log = LogEventos(tmp_path / "gerada.jsonl")
    grafo = construir_grafo_teste(ClienteStub(roteador), log, teto_bootstrap=Decimal("80"))
    resultado = grafo.invoke({"missao_texto": "faça algo"},
                             {"configurable": {"thread_id": "gerada"}})
    assert resultado["spec"]["restricoes"]["teto_custo"] == 80.0
