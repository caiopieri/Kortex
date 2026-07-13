from __future__ import annotations

import math
from typing import Any

import pytest

from motor.curador import certificar_sombra, rodar_sombra


def test_media_de_custos_extremos_permanece_finita_ao_certificar() -> None:
    proposta = {
        "slot": "executor/t1",
        "titular": "modelo-t",
        "candidato": "modelo-c",
        "politica": {"min_casos": 2},
    }
    casos = [{
        "id": str(indice),
        "slot": proposta["slot"],
        "meta": {"split": "held-out", "proveniencia": "suite-h09c"},
        "titular": {"aprovado": indice == 0, "custo_usd": 1e308},
    } for indice in range(2)]
    evidencia = rodar_sombra(
        proposta,
        casos,
        lambda _caso, _modelo: {"aprovado": True, "custo_usd": 1e307},
    )

    resultado = certificar_sombra(evidencia)

    assert evidencia["titular"]["custo_medio_usd"] == 1e308
    assert resultado["status"] == "certificado"
    assert math.isfinite(resultado["titular"]["custo_medio_usd"])
    assert math.isfinite(resultado["candidato"]["custo_medio_usd"])


@pytest.mark.parametrize(
    ("campo", "motivo"),
    [
        ("slot", "identidade da sombra invalida"),
        ("titular", "identidade da sombra invalida"),
        ("candidato", "identidade da sombra invalida"),
        ("id", "ids de casos invalidos ou duplicados"),
        ("proveniencia", "proveniencia held-out invalida"),
    ],
)
def test_identidade_e_proveniencia_whitespace_sao_vetadas(campo: str, motivo: str) -> None:
    proposta: dict[str, Any] = {
        "slot": "executor/t1",
        "titular": "modelo-t",
        "candidato": "modelo-c",
        "politica": {"min_casos": 1},
    }
    caso: dict[str, Any] = {
        "id": "caso-1",
        "slot": proposta["slot"],
        "meta": {"split": "held-out", "proveniencia": "suite-h09c"},
        "titular": {"aprovado": False, "custo_usd": 2.0},
    }
    if campo in proposta:
        proposta[campo] = "   "
        if campo == "slot":
            caso["slot"] = "   "
    elif campo == "id":
        caso["id"] = "   "
    else:
        caso["meta"]["proveniencia"] = "   "

    evidencia = rodar_sombra(
        proposta,
        [caso],
        lambda _caso, _modelo: {"aprovado": True, "custo_usd": 1.0},
    )

    assert certificar_sombra(evidencia)["motivo"] == motivo
