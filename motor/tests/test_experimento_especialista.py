import json
from pathlib import Path

from motor.modelos import ClienteStub
from motor.spec import WorkflowSpec
from scripts.experimento_especialista import formatar_relatorio, preparar_spec, rodar_ab


def _spec_minima() -> dict:
    return {
        "versao": "0.1", "padrao": "grafo_dependencias",
        "missao": {"id": "ab", "objetivo": "CSV para JSON", "contexto": "", "criterios_cobertura": ["schema"]},
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 2, "max_tentativas": 1},
        "subagentes": [
            {"id": "transformador-csv-json", "tipo": "modelo", "papel": "executor", "objetivo": "Converta",
             "entradas": {"csv": "sku,quantidade\nA,1"}, "resultado_esperado": "JSON",
             "rubrica": ["retorna JSON"], "fonte_rag": "__placeholder__", "rag_k": 1},
            {"id": "valida", "tipo": "validador", "valida": "transformador-csv-json",
             "validador": {"kind": "schema_json", "config": {"schema": {
                 "type": "object", "required": ["sku", "quantidade"],
                 "properties": {"sku": {"const": "A"}, "quantidade": {"const": 1}}}}},
             "objetivo": "Validar", "entradas": {}, "resultado_esperado": "Veredito",
             "depende_de": ["transformador-csv-json"]},
        ],
        "gates": [], "sintese": {"instrucao": "sintetize", "formato": "json"},
    }


def test_spec_especialista_csv_json_valida():
    path = Path(__file__).resolve().parents[1] / "exemplos" / "especialista-csv-json.json"
    spec = WorkflowSpec.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert spec.missao.id == "especialista-csv-json"
    assert spec.subagentes[0].fonte_rag
    assert spec.subagentes[1].validador is not None
    assert spec.subagentes[1].validador.kind == "schema_json"


def test_preparar_spec_liga_e_remove_rag():
    spec = _spec_minima()
    assert preparar_spec(spec, "transformador-csv-json", "dataset.jsonl")["subagentes"][0]["fonte_rag"] == "dataset.jsonl"
    assert "fonte_rag" not in preparar_spec(spec, "transformador-csv-json", None)["subagentes"][0]


def test_rodar_ab_agrega_metricas(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(json.dumps({"id": "regra", "conteudo": "Converta CSV em JSON sku A quantidade 1"}) + "\n", encoding="utf-8")

    def barato(papel: str, prompt: str):
        if papel == "executor":
            return '{"sku":"A","quantidade":1}' if "CONTEXTO RECUPERADO" in prompt else '{"sku":"B"}'
        raise AssertionError(papel)

    def topo(papel: str, prompt: str):
        if papel == "executor":
            assert "CONTEXTO RECUPERADO" not in prompt
            return '{"sku":"B","quantidade":1}'
        raise AssertionError(papel)

    resultado = rodar_ab(
        _spec_minima(), alvo="transformador-csv-json", fonte_rag=str(dataset), repeticoes=2,
        barato_factory=lambda: ClienteStub(barato), topo_factory=lambda: ClienteStub(topo),
        workspace_base=tmp_path / "exp", precos={"desconhecido": {"in_por_1k": 0.01, "out_por_1k": 0.02}},
    )
    assert resultado["bracos"]["barato_rag"]["aprovadas"] == 2
    assert resultado["bracos"]["topo_sem_rag"]["aprovadas"] == 0
    assert resultado["bracos"]["barato_rag"]["custo_usd_por_run"] is not None
    relatorio = formatar_relatorio(resultado)
    assert "| barato_rag | 2/2 (100%) |" in relatorio
    assert "| topo_sem_rag | 0/2 (0%) |" in relatorio
