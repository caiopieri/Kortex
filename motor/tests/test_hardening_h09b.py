from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest

from motor.curador import certificar_sombra, preparar_promocao_gated, rodar_sombra
from tests.audit_corpus import casos, executar_lote, materializar_corpus


CASOS_H09B = casos("H09b")


@pytest.fixture(scope="module")
def corpus_h09b(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("corpus-h09b"))


def test_manifest_h09b_tem_dois_casos_e_um_replacement() -> None:
    assert len(CASOS_H09B) == 2


@pytest.fixture(scope="module")
def _lote_h09b(corpus_h09b) -> dict[str, str | None]:
    """Roda os casos deste dono num subprocesso só.

    Um subprocesso por caso pagava ~4,7s de arranque de interpretador para
    milissegundos de trabalho útil. A atribuição por caso continua: cada
    reprodutor abaixo lê o próprio veredito.
    """
    return executar_lote(corpus_h09b, CASOS_H09B)


@pytest.mark.parametrize("nodeid", CASOS_H09B)
def test_reprodutor_h09b(_lote_h09b: dict[str, str | None], nodeid: str) -> None:
    assert _lote_h09b[nodeid] is None, _lote_h09b[nodeid]


class RepoFake:
    def __init__(self, registro: dict[str, Any] | None) -> None:
        self.registro = registro

    def obter(self, certification_id: str) -> dict[str, Any] | None:
        if self.registro is None or self.registro["certification_id"] != certification_id:
            return None
        return self.registro


def _registro(*, candidato_aprova: bool = True) -> dict[str, Any]:
    proposta = {
        "slot": "executor/t1",
        "titular": "modelo-t",
        "candidato": "modelo-c",
        "politica": {"min_casos": 2},
    }
    casos_held_out = [{
        "id": str(indice),
        "slot": proposta["slot"],
        "meta": {"split": "held-out", "proveniencia": "suite-h09b"},
        "titular": {"aprovado": indice == 0, "custo_usd": 2.0},
    } for indice in range(2)]
    evidencia = rodar_sombra(
        proposta,
        casos_held_out,
        lambda _caso, _modelo: {"aprovado": candidato_aprova, "custo_usd": 1.0},
    )
    return {
        "certification_id": "cert-1",
        "evidencia": evidencia,
        "decisao": certificar_sombra(evidencia),
    }


def test_promocao_default_deny_sem_repo_ou_id_conhecido() -> None:
    assert preparar_promocao_gated(cast(Any, {"status": "certificado"}))["status"] == "promocao_vetada"
    assert preparar_promocao_gated("cert-1")["status"] == "promocao_vetada"
    assert preparar_promocao_gated("ausente", RepoFake(_registro()))["status"] == "promocao_vetada"


def test_repo_valido_gera_somente_intencao_gateada_sem_aliases() -> None:
    registro = _registro()
    original = deepcopy(registro)
    eventos: list[str] = []

    intencao = preparar_promocao_gated(
        "cert-1", RepoFake(registro), lambda nome, _payload: eventos.append(nome)
    )
    intencao["evidencia"]["candidato"]["modelo"] = "mutado"

    assert (intencao["status"], intencao["requer_gate"]) == ("promocao_pendente", True)
    assert intencao["certification_id"] == "cert-1"
    assert eventos == ["curador.promocao_pendente"]
    assert "curador.promoveu" not in eventos
    assert registro == original


def test_repo_mutado_divergente_ou_rejeitado_e_vetado() -> None:
    registro = _registro()
    registro["evidencia"]["casos"][0]["candidato"]["aprovado"] = False
    assert preparar_promocao_gated("cert-1", RepoFake(registro))["status"] == "promocao_vetada"

    registro = _registro()
    registro["decisao"]["motivo"] = "decisao adulterada"
    assert preparar_promocao_gated("cert-1", RepoFake(registro))["status"] == "promocao_vetada"

    registro = _registro(candidato_aprova=False)
    assert preparar_promocao_gated("cert-1", RepoFake(registro))["status"] == "promocao_vetada"
