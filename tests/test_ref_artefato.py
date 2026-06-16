import json
import re
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


def _sub(sid: str, depende_de=None, entradas=None, produz_artefatos=None) -> dict:
    return {
        "id": sid,
        "papel": "executor",
        "objetivo": f"Executar {sid}",
        "entradas": entradas or {},
        "resultado_esperado": f"Saída {sid}",
        "rubrica": ["tem saída"],
        "depende_de": depende_de or [],
        "produz_artefatos": produz_artefatos or [],
    }


def _spec(subagentes: list[dict]) -> dict:
    return {
        "versao": "0.1",
        "padrao": "grafo_dependencias",
        "missao": {
            "id": "ref-artefato-teste",
            "objetivo": "Testar referência de artefato",
            "contexto": "",
            "criterios_cobertura": ["subagentes aprovados"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 10, "max_tentativas": 1},
        "subagentes": subagentes,
        "gates": [],
        "sintese": {"instrucao": "Sintetize", "formato": "markdown"},
    }


def test_ref_artefato_resolve_para_caminho_real_em_runtime(tmp_path):
    prompts: dict[str, str] = {}

    def roteador(papel: str, prompt: str):
        if papel == "executor":
            match = re.search(r"subagente '([^']+)'", prompt)
            assert match is not None
            sid = match.group(1)
            prompts[sid] = prompt
            return f"SAIDA {sid}"
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    spec = _spec([
        _sub("A", produz_artefatos=[{"nome": "x.txt", "tipo": "txt"}]),
        _sub("B", depende_de=["A"], entradas={
            "fonte": {"ref_artefato": {"de": "A", "nome": "x.txt"}}
        }),
    ])
    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        ClienteStub(roteador),
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        workspace_base=tmp_path / "runs",
    )

    resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "ref"}})
    caminho = resultado["resultados"][0]["artefatos"][0]["caminho"]

    assert Path(caminho).exists()
    entradas_txt = prompts["B"].split("Entradas: ", 1)[1].split("\nResultado esperado:", 1)[0]
    assert caminho in prompts["B"]
    assert '"ref_artefato"' not in entradas_txt
    assert "SAIDA A" not in entradas_txt


def test_ref_artefato_exige_dependencia_direta():
    spec = _spec([
        _sub("A", produz_artefatos=[{"nome": "x.txt", "tipo": "txt"}]),
        _sub("B", entradas={"fonte": {"ref_artefato": {"de": "A", "nome": "x.txt"}}}),
    ])

    with pytest.raises(ValueError, match="não está em depende_de"):
        WorkflowSpec.model_validate(spec)


def test_ref_artefato_exige_nome_declarado_na_origem():
    spec = _spec([
        _sub("A", produz_artefatos=[{"nome": "x.txt", "tipo": "txt"}]),
        _sub("B", depende_de=["A"], entradas={
            "fonte": {"ref_artefato": {"de": "A", "nome": "outro.txt"}}
        }),
    ])

    with pytest.raises(ValueError, match="não declarado"):
        WorkflowSpec.model_validate(spec)
