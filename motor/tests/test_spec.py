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


def _spec_com_validador_comando() -> dict:
    return {
        "versao": "0.1",
        "padrao": "grafo_dependencias",
        "missao": {
            "id": "validador-comando",
            "objetivo": "Validar saída por comando determinístico",
            "contexto": "",
            "criterios_cobertura": ["produtor validado"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 3, "max_tentativas": 1},
        "subagentes": [
            {
                "id": "produtor",
                "tipo": "modelo",
                "papel": "executor",
                "objetivo": "Produzir arquivo",
                "entradas": {},
                "resultado_esperado": "Arquivo produzido",
                "rubrica": ["entrega arquivo"],
            },
            {
                "id": "valida-produtor",
                "tipo": "validador",
                "valida": "produtor",
                "validador": {"kind": "comando", "config": {"comando": "python -m pytest", "timeout": 60}},
                "objetivo": "Validar produtor por comando",
                "entradas": {},
                "resultado_esperado": "Veredito determinístico",
                "depende_de": ["produtor"],
            },
        ],
        "gates": [],
        "sintese": {"instrucao": "Sintetize", "formato": "markdown"},
    }


def test_validador_comando_valido_sem_papel_ou_rubrica():
    spec = WorkflowSpec.model_validate(_spec_com_validador_comando())
    validador = spec.subagentes[1]
    assert validador.tipo == "validador"
    assert validador.papel is None
    assert validador.rubrica == []
    assert validador.validador is not None
    assert validador.validador.kind == "comando"


def test_validador_comando_exige_config_comando():
    sem_config = _spec_com_validador_comando()
    sem_config["subagentes"][1]["validador"].pop("config")
    with pytest.raises(ValidationError, match="validador.comando.config"):
        WorkflowSpec.model_validate(sem_config)

    sem_comando = _spec_com_validador_comando()
    sem_comando["subagentes"][1]["validador"]["config"].pop("comando")
    with pytest.raises(ValidationError, match="config.comando"):
        WorkflowSpec.model_validate(sem_comando)


def test_validador_comando_exige_valida_em_depende_de():
    sem_valida = _spec_com_validador_comando()
    sem_valida["subagentes"][1].pop("valida")
    with pytest.raises(ValidationError, match="exige valida"):
        WorkflowSpec.model_validate(sem_valida)

    valida_fora_deps = _spec_com_validador_comando()
    valida_fora_deps["subagentes"][1]["depende_de"] = []
    with pytest.raises(ValidationError, match="valida em depende_de"):
        WorkflowSpec.model_validate(valida_fora_deps)
