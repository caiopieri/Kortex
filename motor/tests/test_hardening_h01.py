from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from motor.grafo import _VereditoEvaluator, _decisao_texto
from motor.politica import PoliticaGates
from tests.audit_corpus import casos, executar_caso, materializar_corpus

CASOS = casos("H01")
assert len(CASOS) == 15


@pytest.fixture(scope="session")
def corpus_auditoria(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("audit-corpus-h01"))


@pytest.mark.parametrize("nodeid", CASOS, ids=lambda nodeid: nodeid.split("::", 1)[1])
def test_reprodutor_h01(corpus_auditoria: Path, nodeid: str) -> None:
    executar_caso(corpus_auditoria, nodeid, plugins=("tests.runner_fake",))


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
