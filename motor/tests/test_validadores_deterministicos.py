import json
import sys
from pathlib import Path

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
from tests.runner_fake import RunnerFake


def _sub_modelo(sid: str = "produtor") -> dict:
    return {
        "id": sid,
        "tipo": "modelo",
        "papel": "executor",
        "objetivo": "Produzir saída a validar",
        "entradas": {},
        "resultado_esperado": "Saída textual",
        "rubrica": ["entrega saída"],
    }


def _sub_validador(kind: str, config: dict, alvo: str = "produtor") -> dict:
    return {
        "id": f"valida-{kind}",
        "tipo": "validador",
        "valida": alvo,
        "validador": {"kind": kind, "config": config},
        "objetivo": f"Validar {alvo} por {kind}",
        "entradas": {},
        "resultado_esperado": "Veredito determinístico",
        "depende_de": [alvo],
    }


def _spec(validador: dict) -> dict:
    return {
        "versao": "0.1",
        "padrao": "grafo_dependencias",
        "missao": {
            "id": "validadores",
            "objetivo": "Validar saída por algoritmo",
            "contexto": "",
            "criterios_cobertura": ["produtor validado"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 3, "max_tentativas": 1},
        "subagentes": [_sub_modelo(), validador],
        "gates": [],
        "sintese": {"instrucao": "Sintetize", "formato": "markdown"},
    }


def _eventos(tmp_path):
    return [
        json.loads(linha)
        for linha in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def _script(tmp_path: Path, nome: str, corpo: str) -> Path:
    caminho = tmp_path / nome
    caminho.write_text(corpo, encoding="utf-8")
    return caminho


def _rodar(
    tmp_path,
    spec: dict,
    saidas: list[str],
    cobertura: str = "prosseguir",
    ferramentas_permitidas: list[str] | None = None,
):
    estado = {"executor": 0}

    def roteador(papel: str, prompt: str):
        if papel == "executor":
            estado["executor"] += 1
            indice = min(estado["executor"] - 1, len(saidas) - 1)
            return saidas[indice]
        if papel == "verifier":
            assert "valida-" not in prompt
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"papel inesperado: {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        ClienteStub(roteador),
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": cobertura}),
        workspace_base=tmp_path / "runs",
        ferramentas_permitidas=ferramentas_permitidas,
        command_runner=RunnerFake(),
    )
    resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "validadores"}})
    return resultado, estado, _eventos(tmp_path)


def test_spec_validador_exige_alvo_e_kind_valido():
    sem_alvo = _spec(_sub_validador("contem", {"requer": ["x"]}))
    sem_alvo["subagentes"][1].pop("valida")
    with pytest.raises(ValueError, match="exige valida"):
        WorkflowSpec.model_validate(sem_alvo)

    kind_ruim = _spec(_sub_validador("pytest", {}))
    with pytest.raises(ValueError, match="Input tag 'pytest'"):
        WorkflowSpec.model_validate(kind_ruim)

    dep_ausente = _spec(_sub_validador("contem", {"requer": ["x"]}))
    dep_ausente["subagentes"][1]["depende_de"] = []
    with pytest.raises(ValueError, match="valida em depende_de"):
        WorkflowSpec.model_validate(dep_ausente)


def test_schema_json_aprova_sem_chamar_llm_para_validador(tmp_path):
    schema = {"type": "object", "required": ["nome"], "properties": {"nome": {"type": "string"}}}
    spec = _spec(_sub_validador("schema_json", {"schema": schema}))

    resultado, estado, eventos = _rodar(tmp_path, spec, [json.dumps({"nome": "ok"})])

    assert resultado["resposta_final"] == "FINAL"
    assert estado["executor"] == 1
    validador = next(r for r in resultado["resultados"] if r["id"] == "valida-schema_json")
    assert validador["aprovado"] is True
    evento = next(e for e in eventos if e["evento"] == "validador.rodou")
    assert evento["alvo"] == "produtor"
    assert evento["kind"] == "schema_json"
    assert evento["aprovado"] is True


def test_schema_json_reprova_e_vira_lacuna_do_alvo(tmp_path):
    schema = {"type": "object", "required": ["nome"], "properties": {"nome": {"type": "string"}}}
    spec = _spec(_sub_validador("schema_json", {"schema": schema}))

    resultado, _, eventos = _rodar(tmp_path, spec, [json.dumps({"nome": 123})])

    validador = next(r for r in resultado["resultados"] if r["id"] == "valida-schema_json")
    assert validador["aprovado"] is False
    assert validador["refazer"] == "produtor"
    assert resultado["avaliacao"]["aprovado"] is False
    assert resultado["avaliacao"]["nos_a_refazer"] == ["produtor"]
    assert any(e["evento"] == "validador.rodou" and e["aprovado"] is False for e in eventos)


def test_contem_aprova_e_reprova_por_substring_case_insensitive(tmp_path):
    spec_aprova = _spec(_sub_validador("contem", {"requer": ["Borrow", "Result"], "min": 2}))
    resultado_ok, _, _ = _rodar(tmp_path, spec_aprova, ["usa borrow e result"])
    assert next(r for r in resultado_ok["resultados"] if r["id"] == "valida-contem")["aprovado"] is True

    spec_reprova = _spec(_sub_validador("contem", {"requer": ["borrow", "Result"], "min": 2}))
    resultado_falha, _, eventos = _rodar(tmp_path, spec_reprova, ["usa borrow"])
    validador = next(r for r in resultado_falha["resultados"] if r["id"] == "valida-contem")
    assert validador["aprovado"] is False
    assert "Result" in validador["motivo"]
    assert any(e["evento"] == "validador.rodou" and e["kind"] == "contem" and not e["aprovado"] for e in eventos)


def test_validador_comando_sucesso(tmp_path):
    comando = (
        f"{sys.executable} -c "
        "\"from pathlib import Path; import sys; print(Path.cwd()); "
        "sys.exit(0 if Path.cwd().name == 'artefatos' and sys.argv[1] == 'ok value' else 1)\" "
        "{marcador}"
    )
    validador = _sub_validador("comando", {"comando": comando})
    validador["entradas"] = {"marcador": "ok value"}
    spec = _spec(validador)

    resultado, _, eventos = _rodar(
        tmp_path,
        spec,
        ["saida qualquer"],
        ferramentas_permitidas=[sys.executable],
    )

    item = next(r for r in resultado["resultados"] if r["id"] == "valida-comando")
    assert item["aprovado"] is True
    assert "artefatos" in item["saida"]
    evento = next(e for e in eventos if e["evento"] == "validador.rodou" and e["kind"] == "comando")
    assert evento["aprovado"] is True


def test_validador_comando_falha_redispara_alvo(tmp_path):
    script = _script(
        tmp_path,
        "valida_artefato.py",
        "import pathlib, sys\n"
        "texto = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')\n"
        "print(texto)\n"
        "sys.exit(0 if 'PASSOU' in texto else 1)\n",
    )
    validador = _sub_validador("comando", {"comando": f"{sys.executable} {script} {{arquivo}}"})
    validador["entradas"] = {"arquivo": {"ref_artefato": {"de": "produtor", "nome": "saida.txt"}}}
    spec = _spec(validador)
    spec["subagentes"][0]["produz_artefatos"] = [{"nome": "saida.txt", "tipo": "txt"}]

    resultado, estado, eventos = _rodar(
        tmp_path,
        spec,
        ["primeira versao INVALIDA", "segunda versao PASSOU"],
        cobertura="preencher",
        ferramentas_permitidas=[sys.executable],
    )

    item = next(r for r in resultado["resultados"] if r["id"] == "valida-comando")
    assert item["aprovado"] is True
    assert estado["executor"] == 2
    assert [e["aprovado"] for e in eventos if e["evento"] == "validador.rodou" and e["kind"] == "comando"] == [
        False,
        True,
    ]
    assert [e["subagente"] for e in eventos if e["evento"] == "lacuna.preenchida"] == [
        "produtor",
        "valida-comando",
    ]


def test_comando_reprova_com_stdout_e_refaz_alvo(tmp_path):
    comando = f"{sys.executable} -c \"import sys; print('falha objetiva'); sys.exit(7)\""
    spec = _spec(_sub_validador("comando", {"comando": comando}))

    resultado, _, eventos = _rodar(
        tmp_path,
        spec,
        ["saida qualquer"],
        ferramentas_permitidas=[sys.executable],
    )

    item = next(r for r in resultado["resultados"] if r["id"] == "valida-comando")
    assert item["aprovado"] is False
    assert item["refazer"] == "produtor"
    assert "falha objetiva" in item["motivo"]
    assert resultado["avaliacao"]["nos_a_refazer"] == ["produtor"]
    assert any(e["evento"] == "validador.rodou" and e["kind"] == "comando" and not e["aprovado"] for e in eventos)


def test_validador_comando_bloqueado_por_allowlist(tmp_path, monkeypatch):
    def subprocess_proibido(*args, **kwargs):
        raise AssertionError("subprocess.run não deveria ser chamado")

    monkeypatch.setattr(RunnerFake, "run", subprocess_proibido)
    spec = _spec(_sub_validador("comando", {"comando": "bash -c 'echo nao-roda'"}))

    resultado, _, eventos = _rodar(
        tmp_path,
        spec,
        ["saida qualquer"],
        ferramentas_permitidas=[sys.executable],
    )

    item = next(r for r in resultado["resultados"] if r["id"] == "valida-comando")
    assert item["aprovado"] is False
    assert item["refazer"] == "produtor"
    assert item["motivo"] == "executável não permitido: bash"
    assert any(
        e["evento"] == "validador.rodou"
        and e["kind"] == "comando"
        and e["motivo"] == "executável não permitido: bash"
        for e in eventos
    )


def test_comando_respeita_timeout_configurado(tmp_path):
    comando = f"{sys.executable} -c \"import time; time.sleep(2)\""
    spec = _spec(_sub_validador("comando", {"comando": comando, "timeout": 1}))

    resultado, _, eventos = _rodar(
        tmp_path,
        spec,
        ["saida qualquer"],
        ferramentas_permitidas=[sys.executable],
    )

    item = next(r for r in resultado["resultados"] if r["id"] == "valida-comando")
    assert item["aprovado"] is False
    assert item["refazer"] == "produtor"
    assert item["motivo"] == "timeout ao executar comando"
    assert any(
        e["evento"] == "validador.rodou"
        and e["kind"] == "comando"
        and e["motivo"] == "timeout ao executar comando"
        for e in eventos
    )


def test_reconciliacao_refaz_alvo_validado_nao_so_o_validador(tmp_path):
    spec = _spec(_sub_validador("contem", {"requer": ["token-obrigatorio"]}))

    resultado, estado, eventos = _rodar(
        tmp_path,
        spec,
        ["rascunho sem marcador", "rascunho com token-obrigatorio"],
        cobertura="preencher",
    )

    assert resultado["resposta_final"] == "FINAL"
    assert resultado["avaliacao"]["aprovado"] is True
    assert estado["executor"] == 2
    assert [e["subagente"] for e in eventos if e["evento"] == "lacuna.preenchida"] == [
        "produtor",
        "valida-contem",
    ]
    assert [e["aprovado"] for e in eventos if e["evento"] == "validador.rodou"] == [False, True]
