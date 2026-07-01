import json
from pathlib import Path

from motor.modelos import ClienteStub
from motor.spec import WorkflowSpec
from scripts.experimento_rag import formatar_relatorio, rodar_experimento


def _spec_experimento() -> dict:
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {
            "id": "exp-rag",
            "objetivo": "Corrigir ownership em Rust",
            "contexto": "",
            "criterios_cobertura": ["resposta aprovada"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 1, "max_tentativas": 1},
        "subagentes": [{
            "id": "rust",
            "tipo": "modelo",
            "papel": "executor",
            "objetivo": "corrija ownership move borrow",
            "entradas": {"codigo": "let copia = nome; println!(\"{}\", nome);"},
            "resultado_esperado": "codigo corrigido",
            "rubrica": ["usa contexto quando existir"],
            "fonte_rag": "__placeholder__",
            "rag_k": 1,
        }],
        "gates": [],
        "sintese": {"instrucao": "sintetize", "formato": "markdown"},
    }


def test_experimento_roda_com_e_sem_rag_e_coleta_vereditos(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        json.dumps({"id": "ownership", "conteudo": "ownership move borrow String clone"}) + "\n",
        encoding="utf-8",
    )
    clientes = []

    def roteador(papel: str, prompt: str):
        if papel == "executor":
            return "COM CONTEXTO" if "CONTEXTO RECUPERADO" in prompt else "SEM CONTEXTO"
        if papel == "verifier":
            return json.dumps({
                "aprovado": "COM CONTEXTO" in prompt,
                "motivo": "ok" if "COM CONTEXTO" in prompt else "faltou contexto",
            })
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    def factory():
        cliente = ClienteStub(roteador)
        clientes.append(cliente)
        return cliente

    resultado = rodar_experimento(
        _spec_experimento(), fonte_rag=str(dataset), repeticoes=2,
        cliente_factory=factory, workspace_base=tmp_path / "exp",
    )

    assert resultado["sem_rag"]["aprovadas"] == 0
    assert resultado["com_rag"]["aprovadas"] == 2
    prompts_executor = [p for c in clientes for papel, p in c.chamadas if papel == "executor"]
    assert sum("CONTEXTO RECUPERADO" in p for p in prompts_executor) == 2
    assert sum("CONTEXTO RECUPERADO" not in p for p in prompts_executor) == 2
    relatorio = formatar_relatorio(resultado)
    assert "SEM RAG: 0/2 aprovadas" in relatorio
    assert "COM RAG: 2/2 aprovadas" in relatorio


def test_spec_rag_rust_ownership_valida():
    path = Path(__file__).resolve().parents[1] / "exemplos" / "rag-rust-ownership.json"
    spec = json.loads(path.read_text(encoding="utf-8"))

    validada = WorkflowSpec.model_validate(spec)

    assert validada.missao.id == "rag-rust-ownership"
    assert validada.subagentes[0].fonte_rag
