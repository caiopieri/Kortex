import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from motor.spec import WorkflowSpec

EXEMPLO = json.loads(
    (Path(__file__).parent.parent / "exemplos" / "missao-pesquisa.json").read_text(encoding="utf-8")
)


def test_exemplo_valido():
    spec = WorkflowSpec.model_validate(EXEMPLO)
    assert spec.missao.id == "pesquisa-receita-exemplo"
    assert len(spec.subagentes) == 2
    # roundtrip: serializa e revalida (a spec é dado reexecutável)
    assert WorkflowSpec.model_validate(spec.model_dump()).model_dump() == spec.model_dump()


def test_missao_aceita_template_e_versao_template_opcionais():
    com_template = json.loads(json.dumps(EXEMPLO))
    com_template["missao"]["template"] = "pesquisa"
    com_template["missao"]["versao_template"] = "v2"

    spec = WorkflowSpec.model_validate(com_template)

    assert spec.missao.template == "pesquisa"
    assert spec.missao.versao_template == "v2"
    assert WorkflowSpec.model_validate(EXEMPLO).missao.template is None


def test_versao_nao_suportada():
    ruim = {**EXEMPLO, "versao": "9.9"}
    with pytest.raises(ValidationError, match="não suportada"):
        WorkflowSpec.model_validate(ruim)


def test_ids_duplicados():
    ruim = json.loads(json.dumps(EXEMPLO))
    ruim["subagentes"][1]["id"] = ruim["subagentes"][0]["id"]
    with pytest.raises(ValidationError, match="duplicados"):
        WorkflowSpec.model_validate(ruim)


def test_depende_de_rejeitado_no_v0():
    ruim = json.loads(json.dumps(EXEMPLO))
    ruim["subagentes"][1]["depende_de"] = ["pesquisa-alfa"]
    with pytest.raises(ValidationError, match="depende_de"):
        WorkflowSpec.model_validate(ruim)


def test_sem_subagentes():
    ruim = {**EXEMPLO, "subagentes": []}
    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(ruim)


def test_rubrica_vazia():
    ruim = json.loads(json.dumps(EXEMPLO))
    ruim["subagentes"][0]["rubrica"] = []
    with pytest.raises(ValidationError):
        WorkflowSpec.model_validate(ruim)
