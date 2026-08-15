from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from motor.curador import rodar_sombra
from tests.audit_corpus import casos, executar_lote, materializar_corpus


CASOS_H08 = casos("H08")
PROPOSTA = {"slot": "executor/t1", "titular": "modelo-t", "candidato": "modelo-c"}


@pytest.fixture(scope="module")
def corpus_h08(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("corpus-h08"))


def test_manifest_h08_tem_quatro_casos_autoritativos() -> None:
    assert len(CASOS_H08) == 4


@pytest.fixture(scope="module")
def _lote_h08(corpus_h08) -> dict[str, str | None]:
    """Roda os casos deste dono num subprocesso só.

    Um subprocesso por caso pagava ~4,7s de arranque de interpretador para
    milissegundos de trabalho útil. A atribuição por caso continua: cada
    reprodutor abaixo lê o próprio veredito.
    """
    return executar_lote(corpus_h08, CASOS_H08)


@pytest.mark.parametrize("nodeid", CASOS_H08)
def test_reprodutor_h08(_lote_h08: dict[str, str | None], nodeid: str) -> None:
    assert _lote_h08[nodeid] is None, _lote_h08[nodeid]


def test_runner_e_evidencia_nao_compartilham_aliases_com_held_out() -> None:
    casos_held_out = [{
        "id": "caso-1",
        "slot": PROPOSTA["slot"],
        "entrada": {"texto": "original"},
        "titular": {"aprovado": True, "detalhe": {"fonte": "held-out"}},
    }]
    original = deepcopy(casos_held_out)
    resultado_runner: dict[str, Any] = {
        "aprovado": True,
        "detalhe": {"fonte": "runner"},
    }

    def runner(caso: dict[str, Any], _modelo: str) -> dict[str, Any]:
        caso["entrada"]["texto"] = "mutado"
        caso["titular"]["detalhe"]["fonte"] = "mutada"
        return resultado_runner

    evidencia = rodar_sombra(PROPOSTA, casos_held_out, runner)
    resultado_runner["detalhe"]["fonte"] = "alterada depois"
    evidencia["casos"][0]["titular"]["detalhe"]["fonte"] = "alterada na evidencia"

    assert casos_held_out == original
    assert evidencia["casos"][0]["candidato"]["detalhe"] == {"fonte": "runner"}


def test_excecao_reprova_so_o_caso_e_evidencia_e_repetivel() -> None:
    casos_held_out: list[dict[str, Any]] = [
        {"id": caso_id, "slot": PROPOSTA["slot"], "titular": {"aprovado": True}}
        for caso_id in ("a", "b", "c")
    ]

    def runner(caso: dict[str, Any], _modelo: str) -> dict[str, Any]:
        if caso["id"] == "b":
            raise RuntimeError("runner indisponivel")
        return {"aprovado": True, "motivo": ""}

    primeira = rodar_sombra(PROPOSTA, casos_held_out, runner)
    segunda = rodar_sombra(PROPOSTA, casos_held_out, runner)

    assert primeira == segunda
    assert primeira["candidato"]["total"] == 3
    assert primeira["candidato"]["aprovados"] == 2
    assert primeira["casos"][1]["candidato"] == {
        "aprovado": False,
        "motivo": "RuntimeError: runner indisponivel",
    }
    assert primeira["casos"][2]["candidato"]["aprovado"] is True


def test_falha_ao_copiar_caso_intermediario_nao_aborta_sombra() -> None:
    class IdHostil:
        def __deepcopy__(self, _memo: dict[int, Any]) -> Any:
            raise RuntimeError("deepcopy bloqueado")

    casos_held_out: list[dict[str, Any]] = [
        {"id": "a", "slot": PROPOSTA["slot"], "titular": {"aprovado": True}},
        {"id": IdHostil(), "slot": PROPOSTA["slot"], "titular": {"aprovado": True}},
        {"id": "c", "slot": PROPOSTA["slot"], "titular": {"aprovado": True}},
    ]
    executados: list[str] = []

    def runner(caso: dict[str, Any], _modelo: str) -> dict[str, Any]:
        executados.append(caso["id"])
        return {"aprovado": True, "motivo": ""}

    evidencia = rodar_sombra(PROPOSTA, casos_held_out, runner)

    # Dois modelos por caso: o titular tambem passa pelo runner desde U-04.
    assert executados == ["a", "a", "c", "c"]
    reprovado = {"aprovado": False, "motivo": "RuntimeError: deepcopy bloqueado"}
    assert evidencia["casos"][1] == {
        "id": None,
        "split": None,
        "proveniencia": None,
        # Os DOIS lados reprovam: com o caso incopiavel, nenhum dos modelos foi
        # medido nele. Aproveitar o resultado de um so seria comparar coisas
        # diferentes.
        "titular": reprovado,
        "candidato": reprovado,
    }
    assert evidencia["casos"][2]["candidato"]["aprovado"] is True
