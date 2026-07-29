from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from motor.curador import certificar_sombra, rodar_sombra
from tests.audit_corpus import casos, executar_lote, materializar_corpus


CASOS_H09A = casos("H09a")
PROPOSTA = {
    "slot": "executor/t1",
    "titular": "modelo-t",
    "candidato": "modelo-c",
    "politica": {"min_casos": 2},
}


@pytest.fixture(scope="module")
def corpus_h09a(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("corpus-h09a"))


def test_manifest_h09a_tem_vinte_casos_autoritativos() -> None:
    assert len(CASOS_H09A) == 20


@pytest.fixture(scope="module")
def _lote_h09a(corpus_h09a) -> dict[str, str | None]:
    """Roda os casos deste dono num subprocesso só.

    Um subprocesso por caso pagava ~4,7s de arranque de interpretador para
    milissegundos de trabalho útil. A atribuição por caso continua: cada
    reprodutor abaixo lê o próprio veredito.
    """
    return executar_lote(corpus_h09a, CASOS_H09A)


@pytest.mark.parametrize("nodeid", CASOS_H09A)
def test_reprodutor_h09a(_lote_h09a: dict[str, str | None], nodeid: str) -> None:
    assert _lote_h09a[nodeid] is None, _lote_h09a[nodeid]


def _sombra(
    resultados: list[dict[str, Any]],
    *,
    titular_aprovados: list[bool] | None = None,
    min_casos: int = 2,
    ids: list[str] | None = None,
    split: str = "held-out",
) -> dict[str, Any]:
    aprovacoes = titular_aprovados or [indice == 0 for indice in range(len(resultados))]
    identificadores = ids if ids is not None else [str(i) for i in range(len(resultados))]
    casos_held_out = [{
        "id": identificadores[indice],
        "slot": PROPOSTA["slot"],
        "meta": {"split": split, "proveniencia": "suite-h09a"},
        "titular": {"aprovado": aprovacoes[indice], "custo_usd": 2.0},
    } for indice in range(len(resultados))]
    respostas = iter(resultados)
    proposta = {**PROPOSTA, "politica": {"min_casos": min_casos}}
    return rodar_sombra(proposta, casos_held_out, lambda _caso, _modelo: next(respostas))


def test_certificacao_recomputa_casos_e_ignora_agregados_recebidos() -> None:
    evidencia = _sombra([
        {"aprovado": True, "custo_usd": 1.0},
        {"aprovado": True, "custo_usd": 1.0},
    ])
    evidencia["titular"] = {"modelo": "fraude", "taxa_aprovacao": 1.0, "custo_medio_usd": 0.0}
    evidencia["candidato"] = {"modelo": "fraude", "taxa_aprovacao": 0.0, "custo_medio_usd": 9.0}

    resultado = certificar_sombra(evidencia)

    assert resultado["status"] == "certificado"
    assert resultado["titular"]["taxa_aprovacao"] == 0.5
    assert resultado["candidato"]["taxa_aprovacao"] == 1.0


def test_policy_min_casos_e_selo_sao_precondicoes() -> None:
    evidencia = _sombra([{"aprovado": True, "custo_usd": 1.0}] * 2, min_casos=3)
    assert certificar_sombra(evidencia)["motivo"] == "casos held-out insuficientes"

    evidencia = _sombra([{"aprovado": True, "custo_usd": 1.0}] * 2)
    evidencia["casos"][0]["candidato"]["aprovado"] = False
    assert certificar_sombra(evidencia)["motivo"] == "evidencia de sombra nao selada"

    evidencia = _sombra([{"aprovado": True, "custo_usd": 1.0}] * 2, ids=["x", "x"])
    assert certificar_sombra(evidencia)["motivo"] == "ids de casos invalidos ou duplicados"

    evidencia = _sombra([{"aprovado": True, "custo_usd": 1.0}] * 2, split="treino")
    assert certificar_sombra(evidencia)["motivo"] == "proveniencia held-out invalida"


def test_custo_menor_nao_compensa_regressao_de_qualidade() -> None:
    evidencia = _sombra([
        {"aprovado": True, "custo_usd": 0.01},
        {"aprovado": False, "custo_usd": 0.01},
    ], titular_aprovados=[True, True])

    resultado = certificar_sombra(evidencia)
    assert resultado["status"] == "rejeitado"
    assert "qualidade" in resultado["motivo"]


def test_tipos_e_custo_parcial_sao_validados_nos_casos_selados() -> None:
    evidencia = _sombra([
        {"aprovado": "sim", "custo_usd": 1.0},
        {"aprovado": True, "custo_usd": 1.0},
    ])
    assert certificar_sombra(evidencia)["motivo"] == "aprovado precisa ser bool"

    evidencia = _sombra([
        {"aprovado": True, "custo_usd": 1.0},
        {"aprovado": True},
    ])
    assert certificar_sombra(evidencia)["motivo"] == "custo incomparavel"

    evidencia = _sombra([
        {"aprovado": True, "custo_usd": -1.0},
        {"aprovado": True, "custo_usd": 1.0},
    ])
    assert certificar_sombra(evidencia)["motivo"] == "custo incomparavel"
