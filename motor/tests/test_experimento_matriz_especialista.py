import json
from pathlib import Path

from motor.modelos import ClienteStub
from scripts.experimento_matriz_especialista import _assert_cwd_fora_repo, formatar_relatorio, rodar_matriz
from tests.test_experimento_especialista import _spec_minima


def test_rodar_matriz_agrega_2x2(tmp_path, monkeypatch):
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text(
        json.dumps({"id": "regra", "conteudo": "Converta CSV em JSON sku A quantidade 1"}) + "\n",
        encoding="utf-8",
    )

    def fake_construir_cliente(cfg, registro):
        modelo = cfg["modelo"]

        def roteador(papel: str, prompt: str):
            if papel == "executor":
                if modelo == "pequeno":
                    return '{"sku":"A","quantidade":1}' if "CONTEXTO RECUPERADO" in prompt else '{"sku":"B"}'
                return '{"sku":"A","quantidade":1}'
            raise AssertionError(papel)

        return ClienteStub(roteador)

    monkeypatch.setattr("scripts.experimento_matriz_especialista.construir_cliente", fake_construir_cliente)

    resultado = rodar_matriz(
        _spec_minima(),
        alvo="transformador-csv-json",
        fonte_rag=str(dataset),
        repeticoes=2,
        pequeno_modelos={"modelo": "pequeno"},
        generalista_modelos={"modelo": "generalista"},
        workspace_base=tmp_path / "matriz",
        precos={"desconhecido": {"in_por_1k": 0.01, "out_por_1k": 0.02}},
    )

    assert resultado["celulas"]["pequeno_sem_rag"]["aprovadas"] == 0
    assert resultado["celulas"]["pequeno_com_rag"]["aprovadas"] == 2
    assert resultado["celulas"]["generalista_sem_rag"]["aprovadas"] == 2
    assert resultado["celulas"]["generalista_com_rag"]["aprovadas"] == 2
    assert resultado["isolamento"]["pequeno_sem_rag"]["ls"] == []
    assert resultado["isolamento"]["pequeno_com_rag"]["ls"] == ["fonte.jsonl"]
    relatorio = formatar_relatorio(resultado)
    assert "| pequeno_com_rag | 2/2 (100%) |" in relatorio
    assert "| pequeno_com_rag |" in relatorio
    assert "generalista_sem_rag rodada 1" in relatorio


def test_assert_cwd_fora_repo_rejeita_repo():
    repo = Path(__file__).resolve().parents[2]

    try:
        _assert_cwd_fora_repo(repo)
    except ValueError as exc:
        assert "dentro do repo" in str(exc)
    else:
        raise AssertionError("cwd dentro do repo deveria falhar")
