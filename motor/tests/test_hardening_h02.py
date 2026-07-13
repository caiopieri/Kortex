from __future__ import annotations

import json
from math import inf, nan
from pathlib import Path

import pytest
from pydantic import ValidationError

from motor.spec import WorkflowSpec
from tests.audit_corpus import casos, executar_caso, materializar_corpus

MOTOR = Path(__file__).parents[1]
EXEMPLO = MOTOR / "exemplos/especialista-csv-json.json"
CASOS = casos("H02")
assert len(CASOS) == 14


def _payload_valido() -> dict:
    return json.loads(EXEMPLO.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def corpus_auditoria(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("audit-corpus-h02"))


@pytest.mark.parametrize("nodeid", CASOS, ids=lambda nodeid: nodeid.split("::", 1)[1])
def test_reprodutor_h02(corpus_auditoria: Path, nodeid: str) -> None:
    executar_caso(corpus_auditoria, nodeid)


@pytest.mark.parametrize("capacidade", ["", "   "])
def test_capacidade_vazia_falha_com_restante_da_spec_valido(capacidade: str) -> None:
    payload = _payload_valido()
    payload["subagentes"][0]["capacidades_requeridas"] = [capacidade]
    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(payload)


@pytest.mark.parametrize("custo", [inf, nan, True, False, 0, -1.0])
def test_custo_nao_finito_ou_booleano_falha_com_spec_valida(custo: object) -> None:
    payload = _payload_valido()
    payload["restricoes"]["teto_custo"] = custo
    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(payload)


def test_round_trip_preserva_contratos_validos_e_normaliza_capacidade() -> None:
    payload = _payload_valido()
    payload["restricoes"]["teto_custo"] = 1
    payload["subagentes"][0]["capacidades_requeridas"] = [" codigo "]
    dump = WorkflowSpec.model_validate(payload).model_dump()
    assert dump["restricoes"]["teto_custo"] == 1.0
    assert dump["subagentes"][0]["capacidades_requeridas"] == ["codigo"]
    assert dump["subagentes"][1]["validador"]["config"]["schema"]
