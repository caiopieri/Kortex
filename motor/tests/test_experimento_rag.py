import json
from pathlib import Path

from motor.modelos import ClienteStub
from motor.spec import WorkflowSpec
from scripts.docs_para_rag import gerar_registros
from scripts.experimento_rag import ClienteMetricaDeterministica, formatar_relatorio, rodar_experimento


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


def _spec_experimento_com_contem() -> dict:
    spec = _spec_experimento()
    spec["padrao"] = "grafo_dependencias"
    spec["restricoes"]["max_subagentes"] = 2
    spec["subagentes"].append({
        "id": "valida-termos",
        "tipo": "validador",
        "valida": "rust",
        "validador": {"kind": "contem", "config": {"requer": ["token-rag"], "min": 1}},
        "objetivo": "Validar termo recuperado",
        "entradas": {},
        "resultado_esperado": "Veredito",
        "depende_de": ["rust"],
    })
    return spec


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


def test_experimento_reporta_taxa_do_validador_contem(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        json.dumps({"id": "interno", "conteudo": "ownership move borrow token-rag"}) + "\n",
        encoding="utf-8",
    )

    def roteador(papel: str, prompt: str):
        if papel == "executor":
            return "resposta com token-rag" if "CONTEXTO RECUPERADO" in prompt else "resposta generica"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    resultado = rodar_experimento(
        _spec_experimento_com_contem(), fonte_rag=str(dataset), repeticoes=2,
        cliente_factory=lambda: ClienteStub(roteador), workspace_base=tmp_path / "exp-contem",
    )

    assert resultado["sem_rag"]["contem"]["aprovadas"] == 0
    assert resultado["com_rag"]["contem"]["aprovadas"] == 2
    relatorio = formatar_relatorio(resultado)
    assert "SEM RAG contem: 0/2 aprovadas" in relatorio
    assert "COM RAG contem: 2/2 aprovadas" in relatorio
    assert "contem SEM=False COM=True" in relatorio


def test_cliente_metrica_deterministica_delega_so_executor():
    chamadas = []

    class Base:
        def descricao_de(self, *args, **kwargs):
            return "base"

        def chamar(self, papel, prompt, **kwargs):
            chamadas.append((papel, prompt))
            return "saida real"

    cliente = ClienteMetricaDeterministica(Base())

    assert cliente.descricao_de("executor") == "base"
    assert cliente.chamar("executor", "prompt") == "saida real"
    assert json.loads(cliente.chamar("verifier", "prompt"))["aprovado"] is True
    assert json.loads(cliente.chamar("evaluator", "prompt"))["aprovado"] is True
    assert cliente.chamar("synthesizer", "prompt") == "FINAL"
    assert chamadas == [("executor", "prompt")]


def test_spec_rag_rust_ownership_valida():
    path = Path(__file__).resolve().parents[1] / "exemplos" / "rag-rust-ownership.json"
    spec = json.loads(path.read_text(encoding="utf-8"))

    validada = WorkflowSpec.model_validate(spec)

    assert validada.missao.id == "rag-rust-ownership"
    assert validada.subagentes[0].fonte_rag


def test_docs_para_rag_gera_jsonl_com_conteudo_e_origem(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "interno.md").write_text(
        "# Titulo\n\nParagrafo um sobre prevenção.\n\n## Secao\n\nTexto sobre gate de cobertura.",
        encoding="utf-8",
    )

    registros = gerar_registros([docs], max_chars=80)

    assert registros
    assert all(registro["conteudo"].strip() for registro in registros)
    assert all(registro["origem"] for registro in registros)
    assert any("prevenção" in registro["conteudo"] for registro in registros)


def test_spec_lift_docs_metafabrica_valida():
    path = Path(__file__).resolve().parents[1] / "exemplos" / "lift-docs-metafabrica.json"
    spec = json.loads(path.read_text(encoding="utf-8"))

    validada = WorkflowSpec.model_validate(spec)

    assert validada.missao.id == "lift-docs-metafabrica"
    validador = next(sub for sub in validada.subagentes if sub.tipo == "validador")
    assert validador.validador["kind"] == "contem"
    assert validador.validador["config"]["min"] == 5
