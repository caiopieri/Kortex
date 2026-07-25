import json
import re

import pytest

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.eventos import LogEventos
from tests.helpers_grafo import construir_grafo_teste as construir_grafo
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates
from motor.spec import WorkflowSpec


def _sub(sid: str, depende_de: list[str] | None = None) -> dict:
    return {
        "id": sid,
        "papel": "executor",
        "objetivo": f"Executar etapa {sid}",
        "entradas": {},
        "resultado_esperado": f"Saída da etapa {sid}",
        "rubrica": ["entrega saída textual"],
        "depende_de": depende_de or [],
    }


def _spec(subagentes: list[dict], padrao: str = "grafo_dependencias") -> dict:
    return {
        "versao": "0.1",
        "padrao": padrao,
        "missao": {
            "id": "grafo-dep-teste",
            "objetivo": "Validar execução por dependências",
            "contexto": "",
            "criterios_cobertura": ["todos os subagentes aprovados"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 10, "max_tentativas": 1},
        "subagentes": subagentes,
        "gates": [],
        "sintese": {"instrucao": "Sintetize", "formato": "markdown"},
    }


def _rodar(tmp_path, spec: dict):
    ordem: list[str] = []
    prompts: dict[str, str] = {}

    def roteador(papel: str, prompt: str):
        if papel == "executor":
            match = re.search(r"subagente '([^']+)'", prompt)
            assert match is not None
            sid = match.group(1)
            ordem.append(sid)
            prompts[sid] = prompt
            return f"SAIDA {sid}"
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
    )
    resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "grafo-dep"}})
    eventos = [
        json.loads(linha)
        for linha in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return resultado, ordem, prompts, eventos


def test_cadeia_executa_em_ordem_e_injeta_dependencia(tmp_path):
    spec = _spec([_sub("A"), _sub("B", ["A"]), _sub("C", ["B"]), _sub("D", ["C"])])

    resultado, ordem, prompts, _ = _rodar(tmp_path, spec)

    assert resultado["resposta_final"] == "FINAL"
    assert ordem == ["A", "B", "C", "D"]
    assert "\nResultados das dependências:\n- A: SAIDA A" in prompts["B"]


def test_diamante_respeita_ordem_topologica(tmp_path):
    spec = _spec([_sub("A"), _sub("B", ["A"]), _sub("C", ["A"]), _sub("D", ["B", "C"])])

    _, ordem, prompts, eventos = _rodar(tmp_path, spec)

    assert ordem.index("A") < ordem.index("B")
    assert ordem.index("A") < ordem.index("C")
    assert ordem.index("D") > ordem.index("B")
    assert ordem.index("D") > ordem.index("C")
    assert "- B: SAIDA B" in prompts["D"]
    assert "- C: SAIDA C" in prompts["D"]
    arestas = [(e["de"], e["para"]) for e in eventos if e["evento"] == "aresta.fluxo"]
    assert arestas == [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]


def test_ciclo_em_grafo_dependencias_rejeitado():
    spec = _spec([_sub("A", ["B"]), _sub("B", ["A"])])

    with pytest.raises(ValueError, match="ciclo.*A.*B"):
        WorkflowSpec.model_validate(spec)


def test_dependencia_inexistente_rejeitada():
    spec = _spec([_sub("A", ["zzz"])])

    with pytest.raises(ValueError, match="zzz"):
        WorkflowSpec.model_validate(spec)


def test_fan_out_continua_rejeitando_depende_de():
    spec = _spec([_sub("A"), _sub("B", ["A"])], padrao="fan_out_sintese")

    with pytest.raises(ValueError, match="fan_out_sintese.*depende_de|depende_de.*fan_out_sintese"):
        WorkflowSpec.model_validate(spec)


def test_fan_out_sem_deps_nao_injeta_secao_no_prompt(tmp_path):
    spec = _spec([_sub("A"), _sub("B")], padrao="fan_out_sintese")

    _, ordem, prompts, _ = _rodar(tmp_path, spec)

    assert set(ordem) == {"A", "B"}
    assert all("Resultados das dependências" not in prompt for prompt in prompts.values())
