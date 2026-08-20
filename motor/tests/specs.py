"""Specs mínimas pertencentes aos testes, independentes de ``exemplos/``."""

from __future__ import annotations

import json
from typing import Any


def _missao() -> dict[str, Any]:
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {
            "id": "pesquisa-receita-exemplo",
            "objetivo": "Levantar oportunidades de aumento de receita",
            "contexto": "Marketplace e possibilidade de receita recorrente",
            "criterios_cobertura": [
                "canal de anúncios em marketplace coberto com evidência",
                "canal de receita recorrente coberto com evidência",
            ],
        },
        "restricoes": {"teto_custo": 60.0, "max_subagentes": 10, "max_tentativas": 3},
        "gates": [],
        "sintese": {
            "instrucao": "Consolide as oportunidades em um relatório ranqueado",
            "formato": "markdown",
        },
    }


def _subagente(
    identificador: str, objetivo: str, entradas: dict[str, Any], resultado: str,
) -> dict[str, Any]:
    return {
        "id": identificador,
        "papel": "pesquisador",
        "objetivo": objetivo,
        "entradas": entradas,
        "resultado_esperado": resultado,
        "rubrica": [
            "cita evidência ou fonte",
            "específico e acionável",
            "3 ou mais oportunidades",
        ],
    }


def spec_pesquisa() -> dict[str, Any]:
    """Fixture de dois subagentes para testes de fan-out e serviço."""
    spec = _missao()
    spec["subagentes"] = [
        _subagente(
            "pesquisa-alfa",
            "Investigar oportunidades no canal alfa: anúncios em marketplaces",
            {"canais": ["Mercado Livre", "Shopee"]},
            "3+ oportunidades específicas, cada uma com evidência",
        ),
        _subagente(
            "pesquisa-beta",
            "Investigar oportunidades no canal beta: receita recorrente",
            {},
            "3+ oportunidades específicas, cada uma com evidência",
        ),
    ]
    return spec


def spec_pesquisa_um() -> dict[str, Any]:
    """Fixture de um subagente para testes de uma única tarefa."""
    spec = _missao()
    spec["subagentes"] = [
        _subagente(
            "pesquisa-alfa",
            "Investigar oportunidades no canal alfa",
            {"canais": ["Mercado Livre", "Shopee"]},
            "3+ oportunidades específicas, cada uma com evidência",
        ),
    ]
    return spec


SPEC = spec_pesquisa()


def faz_roteador(reprovar_beta_uma_vez: bool = False, evaluator_aprova: bool = True):
    """Stub determinístico por papel; identifica o subagente pelo prompt."""
    estado = {"beta_reprovado": False}

    def roteador(papel: str, prompt: str):
        if papel == "planner":
            return json.dumps(SPEC, ensure_ascii=False)
        if papel == "pesquisador":
            return "RESULTADO alfa" if "pesquisa-alfa" in prompt else "RESULTADO beta"
        if papel == "verifier":
            if reprovar_beta_uma_vez and "pesquisa-beta" in prompt and not estado["beta_reprovado"]:
                estado["beta_reprovado"] = True
                return json.dumps({"aprovado": False, "motivo": "faltou evidência"})
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            if evaluator_aprova:
                return json.dumps({"aprovado": True, "lacunas": []})
            return json.dumps({"aprovado": False, "lacunas": ["canal beta sem evidência"]})
        if papel == "synthesizer":
            return "SÍNTESE FINAL DA MISSÃO"
        raise AssertionError(f"papel inesperado: {papel}")

    return roteador
