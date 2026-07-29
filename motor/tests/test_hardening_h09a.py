from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from motor.curador import PISO_CASOS, certificar_sombra, rodar_sombra
from tests.audit_corpus import casos, executar_lote, materializar_corpus


CASOS_H09A = casos("H09a")
PROPOSTA = {
    "slot": "executor/t1",
    "titular": "modelo-t",
    "candidato": "modelo-c",
    "politica": {"min_casos": PISO_CASOS},
}
CHAVE = b"chave-de-teste-h09a-com-32-bytes!!"


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
    min_casos: int = PISO_CASOS,
    ids: list[str] | None = None,
    split: str = "held-out",
    pad_favorece_candidato: bool = True,
) -> dict[str, Any]:
    """Monta uma sombra com os casos declarados, completada ate o piso.

    O piso de PISO_CASOS existe para impedir certificacao com amostra minuscula
    (U-07), e cada teste aqui quer provar OUTRA coisa -- selo, tipo, custo. O
    enchimento leva a amostra ate o piso sem mexer no que o teste mede.

    `pad_favorece_candidato` escolhe o enchimento: discordante a favor do
    candidato (para o teste chegar ao eixo de custo, atravessando a significancia)
    ou concordante (para o teste medir a propria regressao de qualidade).
    """
    n = len(resultados)
    aprovacoes = titular_aprovados or [indice == 0 for indice in range(n)]
    identificadores = ids if ids is not None else [str(i) for i in range(n)]

    total = max(n, PISO_CASOS)
    casos_held_out = [{
        "id": identificadores[indice] if indice < n else f"pad-{indice}",
        "slot": PROPOSTA["slot"],
        "meta": {"split": split, "proveniencia": "suite-h09a"},
    } for indice in range(total)]

    def runner(caso: dict[str, Any], modelo: str) -> dict[str, Any]:
        indice = next(
            (i for i, c in enumerate(casos_held_out) if c["id"] == caso["id"]), -1,
        )
        if indice < n:
            if modelo == "modelo-t":
                return {"aprovado": aprovacoes[indice], "custo_usd": 2.0}
            return dict(resultados[indice])
        if modelo == "modelo-t":
            return {"aprovado": not pad_favorece_candidato, "custo_usd": 2.0}
        return {"aprovado": True, "custo_usd": 1.0}

    proposta = {**PROPOSTA, "politica": {"min_casos": min_casos}}
    return rodar_sombra(proposta, casos_held_out, runner, chave=CHAVE)


def test_certificacao_recomputa_casos_e_ignora_agregados_recebidos() -> None:
    evidencia = _sombra([
        {"aprovado": True, "custo_usd": 1.0},
        {"aprovado": True, "custo_usd": 1.0},
    ])
    evidencia["titular"] = {"modelo": "fraude", "taxa_aprovacao": 1.0, "custo_medio_usd": 0.0}
    evidencia["candidato"] = {"modelo": "fraude", "taxa_aprovacao": 0.0, "custo_medio_usd": 9.0}

    resultado = certificar_sombra(evidencia, chave=CHAVE)

    assert resultado["status"] == "certificado"
    # Os agregados plantados sumiram: modelo, taxa e custo saem dos casos.
    assert resultado["titular"]["modelo"] == "modelo-t"
    assert resultado["titular"]["taxa_aprovacao"] == round(1 / PISO_CASOS, 4)
    assert resultado["titular"]["custo_medio_usd"] == 2.0
    assert resultado["candidato"]["taxa_aprovacao"] == 1.0


def test_policy_min_casos_e_selo_sao_precondicoes() -> None:
    # Politica que promete mais casos do que a sombra rodou.
    evidencia = _sombra([{"aprovado": True, "custo_usd": 1.0}] * 2, min_casos=PISO_CASOS + 5)
    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == "casos held-out insuficientes"

    # E politica abaixo do piso do sistema: o proponente nao escolhe o rigor.
    evidencia = _sombra([{"aprovado": True, "custo_usd": 1.0}] * 2, min_casos=2)
    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == (
        f"politica min_casos invalida: piso e {PISO_CASOS}"
    )

    evidencia = _sombra([{"aprovado": True, "custo_usd": 1.0}] * 2)
    evidencia["casos"][0]["candidato"]["aprovado"] = False
    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == "evidencia de sombra nao selada"

    evidencia = _sombra([{"aprovado": True, "custo_usd": 1.0}] * 2, ids=["x", "x"])
    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == "ids de casos invalidos ou duplicados"

    evidencia = _sombra([{"aprovado": True, "custo_usd": 1.0}] * 2, split="treino")
    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == "proveniencia held-out invalida"


def test_custo_menor_nao_compensa_regressao_de_qualidade() -> None:
    evidencia = _sombra([
        {"aprovado": True, "custo_usd": 0.01},
        {"aprovado": False, "custo_usd": 0.01},
    ], titular_aprovados=[True, True], pad_favorece_candidato=False)

    resultado = certificar_sombra(evidencia, chave=CHAVE)
    assert resultado["status"] == "rejeitado"
    assert "qualidade" in resultado["motivo"]


def test_tipos_e_custo_parcial_sao_validados_nos_casos_selados() -> None:
    evidencia = _sombra([
        {"aprovado": "sim", "custo_usd": 1.0},
        {"aprovado": True, "custo_usd": 1.0},
    ])
    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == "aprovado precisa ser bool"

    evidencia = _sombra([
        {"aprovado": True, "custo_usd": 1.0},
        {"aprovado": True},
    ])
    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == "custo incomparavel"

    evidencia = _sombra([
        {"aprovado": True, "custo_usd": -1.0},
        {"aprovado": True, "custo_usd": 1.0},
    ])
    assert certificar_sombra(evidencia, chave=CHAVE)["motivo"] == "custo incomparavel"
