from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from motor.grafo import _VereditoEvaluator, _decisao_texto
from motor.politica import PoliticaGates
from tests.audit_corpus import casos, executar_lote, materializar_corpus

CASOS = casos("H01")
assert len(CASOS) == 15


@pytest.fixture(scope="session")
def corpus_auditoria(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("audit-corpus-h01"))


@pytest.fixture(scope="module")
def _lote_h01(corpus_auditoria) -> dict[str, str | None]:
    """Roda os casos deste dono num subprocesso só.

    Um subprocesso por caso pagava ~4,7s de arranque de interpretador para
    milissegundos de trabalho útil. A atribuição por caso continua: cada
    reprodutor abaixo lê o próprio veredito.
    """
    return executar_lote(corpus_auditoria, CASOS, plugins=("tests.runner_fake",))


@pytest.mark.parametrize("nodeid", CASOS, ids=lambda nodeid: nodeid.split("::", 1)[1])
def test_reprodutor_h01(_lote_h01: dict[str, str | None], nodeid: str) -> None:
    assert _lote_h01[nodeid] is None, _lote_h01[nodeid]


def test_policy_default_e_mutacao_continuam_estritos() -> None:
    politica = PoliticaGates(auto_mode=True)
    assert politica.decisao_auto("plano") == "prosseguir"
    with pytest.raises(ValueError, match="default"):
        politica.decisao_auto("plano", default="")
    politica.overrides["cobertura"] = "talvez"
    with pytest.raises(ValueError, match="decisao"):
        politica.decisao_auto("cobertura")


def test_decisao_nao_string_e_evaluator_contraditorio_falham_fechado() -> None:
    assert _decisao_texto({"decisao": "prosseguir"}) is None
    with pytest.raises(ValidationError):
        _VereditoEvaluator(aprovado=True, lacunas=["ainda falta evidencia"])
