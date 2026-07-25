from math import inf

import pytest
from pydantic import ValidationError

from motor.politica import politica_de_config
from motor.spec import WorkflowSpec


def _spec_payload() -> dict:
    return {
        "versao": "0.1",
        "padrao": "grafo_dependencias",
        "missao": {
            "id": "missao",
            "objetivo": "produzir resultado",
            "criterios_cobertura": ["resultado validado"],
        },
        "subagentes": [
            {
                "id": "executor",
                "tipo": "modelo",
                "papel": "redator",
                "objetivo": "produzir",
                "resultado_esperado": "texto",
                "rubrica": ["correto"],
            },
            {
                "id": "validador",
                "tipo": "validador",
                "valida": "executor",
                "depende_de": ["executor"],
                "validador": {"kind": "schema_json", "config": {}},
                "objetivo": "validar",
                "resultado_esperado": "aprovado ou reprovado",
            },
        ],
        "sintese": {"instrucao": "sintetizar"},
    }


@pytest.mark.parametrize("kind", ["schema_json", "contem"])
def test_s1_rejeita_validador_sem_config(kind: str) -> None:
    payload = _spec_payload()
    payload["subagentes"][1]["validador"] = {"kind": kind}

    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(payload)


@pytest.mark.parametrize(
    "config",
    [
        {"comando": "   "},
        {"comando": "echo ok", "timeout": 0},
        {"comando": "echo ok", "timeout": True},
    ],
)
def test_s1_rejeita_config_comando_sem_valor_executavel(config: dict) -> None:
    payload = _spec_payload()
    payload["subagentes"][1]["validador"] = {
        "kind": "comando",
        "config": config,
    }

    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(payload)


@pytest.mark.parametrize("capacidade", ["", "   "])
def test_s3_rejeita_capacidade_declarada_vazia(capacidade: str) -> None:
    payload = _spec_payload()
    payload["subagentes"][0]["capacidades_requeridas"] = [capacidade]

    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(payload)


@pytest.mark.parametrize("teto_custo", [inf, True])
def test_s4_rejeita_teto_que_nao_seja_numero_finito(teto_custo: object) -> None:
    payload = _spec_payload()
    payload["restricoes"] = {"teto_custo": teto_custo}

    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(payload)


@pytest.mark.parametrize("auto_mode", ["false", 1])
def test_politica_rejeita_auto_mode_nao_booleano(auto_mode: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        politica_de_config({"auto_mode": auto_mode})


@pytest.mark.parametrize("decisao", ["", 1])
def test_politica_rejeita_override_sem_decisao_valida(decisao: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        politica_de_config({"gates": {"cobertura": decisao}})
