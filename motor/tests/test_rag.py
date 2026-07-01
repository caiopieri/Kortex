import json

from motor.rag import carregar_dataset, recuperar


def test_carregar_dataset_ignora_linhas_malformadas_e_sem_conteudo(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        "\n".join([
            json.dumps({"id": "a", "conteudo": "borrow checker move"}),
            "{json quebrado",
            json.dumps({"id": "b", "texto": "sem conteudo"}),
            json.dumps(["lista"]),
            json.dumps({"id": "c", "conteudo": "Result com ?"}),
        ]),
        encoding="utf-8",
    )

    registros = carregar_dataset(dataset)

    assert [r["id"] for r in registros] == ["a", "c"]


def test_carregar_dataset_inexistente_devolve_vazio(tmp_path):
    assert carregar_dataset(tmp_path / "ausente.jsonl") == []


def test_recuperar_ranqueia_por_overlap_case_insensitive():
    dataset = [
        {"id": "irrelevante", "conteudo": "lifetime generics trait"},
        {"id": "move", "conteudo": "Ownership move borrow checker"},
        {"id": "result", "conteudo": "Result error handling com operador ?"},
    ]

    recs = recuperar(dataset, "corrija ownership move e borrow", k=2)

    assert [r["id"] for r in recs] == ["move"]
