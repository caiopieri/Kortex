from __future__ import annotations

import math
from typing import Any

import pytest

from motor.curador import PISO_CASOS, certificar_sombra, rodar_sombra

CHAVE = b"chave-de-teste-h09c-com-32-bytes!!"


def test_media_de_custos_extremos_permanece_finita_ao_certificar() -> None:
    proposta = {
        "slot": "executor/t1",
        "titular": "modelo-t",
        "candidato": "modelo-c",
        "politica": {"min_casos": PISO_CASOS},
    }
    casos = [{
        "id": str(indice),
        "slot": proposta["slot"],
        "meta": {"split": "held-out", "proveniencia": "suite-h09c"},
    } for indice in range(PISO_CASOS)]

    def runner(caso: dict[str, Any], modelo: str) -> dict[str, Any]:
        if modelo == "modelo-t":
            return {"aprovado": caso["id"] == "0", "custo_usd": 1e308}
        return {"aprovado": True, "custo_usd": 1e307}

    evidencia = rodar_sombra(proposta, casos, runner, chave=CHAVE)

    resultado = certificar_sombra(evidencia, chave=CHAVE)

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
        "politica": {"min_casos": PISO_CASOS},
    }
    # PISO_CASOS casos identicos no que importa: o veto testado e de identidade,
    # nao de tamanho de amostra, e com menos que o piso a rejeicao viria pelo
    # motivo errado -- o teste passaria medindo outra coisa.
    casos: list[dict[str, Any]] = [{
        "id": f"caso-{indice}",
        "slot": proposta["slot"],
        "meta": {"split": "held-out", "proveniencia": "suite-h09c"},
    } for indice in range(PISO_CASOS)]
    caso = casos[0]
    if campo in proposta:
        proposta[campo] = "   "
        if campo == "slot":
            for outro in casos:
                outro["slot"] = "   "
    elif campo == "id":
        caso["id"] = "   "
    else:
        caso["meta"]["proveniencia"] = "   "

    evidencia = rodar_sombra(
        proposta,
        casos,
        lambda _caso, modelo: {"aprovado": modelo == "modelo-c", "custo_usd": 1.0},
        chave=CHAVE,
    )

    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == motivo
