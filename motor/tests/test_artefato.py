import hashlib
import json
from pathlib import Path

import pytest

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates
from motor.spec import WorkflowSpec


def _sub(produz_artefatos=None) -> dict:
    return {
        "id": "autor",
        "papel": "executor",
        "objetivo": "Gerar texto",
        "entradas": {},
        "resultado_esperado": "Texto final",
        "rubrica": ["tem texto"],
        "produz_artefatos": produz_artefatos or [],
    }


def _spec(sub: dict) -> dict:
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {
            "id": "artefato-teste",
            "objetivo": "Testar artefato",
            "contexto": "",
            "criterios_cobertura": ["subagente aprovado"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 10, "max_tentativas": 1},
        "subagentes": [sub],
        "gates": [],
        "sintese": {"instrucao": "Sintetize", "formato": "markdown"},
    }


def _rodar(tmp_path, spec: dict, saida: str = "CONTEUDO FIXO"):
    def roteador(papel: str, prompt: str):
        if papel == "executor":
            return saida
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        ClienteStub(roteador),
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        workspace_base=tmp_path / "runs",
    )
    resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "artefato"}})
    eventos = [
        json.loads(linha)
        for linha in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return resultado, eventos


def test_modelo_produz_artefato_em_workspace_com_hash(tmp_path):
    texto = "CONTEUDO FIXO"
    resultado, eventos = _rodar(tmp_path, _spec(_sub([{"nome": "saida.txt", "tipo": "txt"}])), texto)

    ref = resultado["resultados"][0]["artefatos"][0]
    caminho = Path(ref["caminho"])

    assert caminho.exists()
    assert caminho.name == "autor__saida.txt"
    assert caminho.read_text(encoding="utf-8") == texto
    assert ref == {
        "nome": "saida.txt",
        "caminho": str(caminho),
        "tipo": "txt",
        "hash": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
    }
    assert any(
        evento["evento"] == "artefato.atualizou"
        and evento["nome"] == "saida.txt"
        and evento["tipo"] == "txt"
        and evento["subagente"] == "autor"
        and evento["caminho"] == str(caminho)
        for evento in eventos
    )


def test_estado_carrega_referencia_sem_conteudo_no_artefato(tmp_path):
    texto = "CONTEUDO FIXO"
    resultado, _ = _rodar(tmp_path, _spec(_sub([{"nome": "saida.txt", "tipo": "txt"}])), texto)

    item = resultado["resultados"][0]

    assert item["saida"] == texto
    assert texto not in json.dumps(item["artefatos"], ensure_ascii=False)
    assert set(item["artefatos"][0]) == {"nome", "caminho", "tipo", "hash"}


def test_sem_producao_nao_adiciona_chave_artefatos(tmp_path):
    resultado, _ = _rodar(tmp_path, _spec(_sub()))

    assert "artefatos" not in resultado["resultados"][0]


def test_modelo_com_multiplos_artefatos_rejeitado():
    spec = _spec(_sub([
        {"nome": "a.txt", "tipo": "txt"},
        {"nome": "b.txt", "tipo": "txt"},
    ]))

    with pytest.raises(ValueError, match="mais de um artefato"):
        WorkflowSpec.model_validate(spec)
