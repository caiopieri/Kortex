import json
import sys
from pathlib import Path
from types import SimpleNamespace

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor import __main__ as cli
from motor.eventos import LogEventos
from tests.helpers_grafo import construir_grafo_teste as construir_grafo
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates
from motor.registro import ferramentas_de_registro, ferramentas_permitidas_de_registro
from tests.runner_fake import RunnerFake


def _tool_sub(nome="fake", entradas=None) -> dict:
    return {
        "id": "check",
        "tipo": "ferramenta",
        "ferramenta": nome,
        "objetivo": "Executar checagem determinística",
        "entradas": entradas or {},
        "resultado_esperado": "Exit code objetivo",
    }


def _spec(sub: dict) -> dict:
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {
            "id": "ferramenta-teste",
            "objetivo": "Testar ferramenta",
            "contexto": "",
            "criterios_cobertura": ["ferramenta executada"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 10, "max_tentativas": 1},
        "subagentes": [sub],
        "gates": [],
        "sintese": {"instrucao": "Sintetize", "formato": "markdown"},
    }


def _script(tmp_path, nome: str, corpo: str) -> Path:
    caminho = tmp_path / nome
    caminho.write_text(corpo, encoding="utf-8")
    return caminho


_POLITICA_PADRAO = object()


def _rodar(tmp_path, spec: dict, ferramentas: dict, ferramentas_permitidas=_POLITICA_PADRAO):
    def roteador(papel: str, prompt: str):
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(f"modelo não deveria ser chamado para papel {papel}")

    log = LogEventos(tmp_path / "log.jsonl")
    permitidas = [sys.executable] if ferramentas_permitidas is _POLITICA_PADRAO else ferramentas_permitidas
    grafo = construir_grafo(
        ClienteStub(roteador),
        log,
        checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "prosseguir"}),
        workspace_base=tmp_path / "runs",
        ferramentas=ferramentas,
        ferramentas_permitidas=permitidas,
        command_runner=RunnerFake(),
    )
    resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "ferramenta"}})
    eventos = [
        json.loads(linha)
        for linha in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    return resultado, eventos


def test_ferramenta_registrada_com_exit_zero_aprova(tmp_path):
    script = _script(tmp_path, "ok.py", "print('ok')\n")
    ferramentas = {"fake": {"comando": f"{sys.executable} {script}", "interpreta_saida": "exit_code"}}

    resultado, eventos = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    item = resultado["resultados"][0]
    assert item["aprovado"] is True
    assert item["saida"] == "ok"
    assert any(e["evento"] == "ferramenta.executada" and e["aprovado"] is True for e in eventos)


def test_ferramenta_com_exit_um_reprova_com_stdout_no_motivo(tmp_path):
    script = _script(tmp_path, "falha.py", "import sys\nprint('erro objetivo')\nsys.exit(1)\n")
    ferramentas = {"fake": {"comando": f"{sys.executable} {script}", "interpreta_saida": "exit_code"}}

    resultado, eventos = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    item = resultado["resultados"][0]
    assert item["aprovado"] is False
    assert "erro objetivo" in item["motivo"]
    assert any(e["evento"] == "ferramenta.executada" and e["aprovado"] is False for e in eventos)


def test_ferramenta_respeita_timeout_configurado(tmp_path):
    script = _script(tmp_path, "dorme.py", "import time\ntime.sleep(0.1)\nprint('ok')\n")
    ferramentas = {
        "fake": {
            "comando": f"{sys.executable} {script}",
            "interpreta_saida": "exit_code",
            "timeout": 1,
        }
    }

    resultado, _ = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    item = resultado["resultados"][0]
    assert item["aprovado"] is True
    assert item["saida"] == "ok"


def test_ferramenta_timeout_curto_reprova(tmp_path):
    script = _script(tmp_path, "dorme.py", "import time\ntime.sleep(0.1)\nprint('ok')\n")
    ferramentas = {
        "fake": {
            "comando": f"{sys.executable} {script}",
            "interpreta_saida": "exit_code",
            "timeout": 0,
        }
    }

    resultado, eventos = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    item = resultado["resultados"][0]
    assert item["aprovado"] is False
    assert item["motivo"] == "timeout ao executar ferramenta"
    assert any(e["evento"] == "ferramenta.executada" and e["aprovado"] is False for e in eventos)


def test_ferramenta_json_aprova_e_registra_metricas(tmp_path):
    script = _script(
        tmp_path,
        "json_ok.py",
        "import json, sys\n"
        "print(json.dumps({'aprovado': True, 'metricas': {'fs_escoamento': 2.1}, 'motivo': ''}))\n"
        "sys.stderr.write('aviso no stderr')\n",
    )
    ferramentas = {"fake": {"comando": f"{sys.executable} {script}", "interpreta_saida": "json"}}

    resultado, eventos = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    item = resultado["resultados"][0]
    assert item["aprovado"] is True
    assert item["metricas"] == {"fs_escoamento": 2.1}
    assert "aviso no stderr" in item["saida"]
    assert any(e["evento"] == "ferramenta.executada"
               and e["metricas"] == {"fs_escoamento": 2.1}
               for e in eventos)


def test_ferramenta_json_aprovado_false_usa_motivo(tmp_path):
    script = _script(
        tmp_path,
        "json_reprova.py",
        "import json\nprint(json.dumps({'aprovado': False, 'metricas': {'x': 1}, 'motivo': 'fora da tolerancia'}))\n",
    )
    ferramentas = {"fake": {"comando": f"{sys.executable} {script}", "interpreta_saida": "json"}}

    resultado, _ = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    item = resultado["resultados"][0]
    assert item["aprovado"] is False
    assert item["motivo"] == "fora da tolerancia"
    assert item["metricas"] == {"x": 1}


def test_ferramenta_json_invalido_reprova_e_emite_evento(tmp_path):
    script = _script(tmp_path, "json_invalido.py", "print('nao-json')\n")
    ferramentas = {"fake": {"comando": f"{sys.executable} {script}", "interpreta_saida": "json"}}

    resultado, eventos = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    item = resultado["resultados"][0]
    assert item["aprovado"] is False
    assert item["motivo"].startswith("saída inválida:")
    assert any(e["evento"] == "ferramenta.saida_invalida" for e in eventos)


def test_ferramenta_json_sem_aprovado_reprova_e_emite_evento(tmp_path):
    script = _script(tmp_path, "json_sem_aprovado.py", "import json\nprint(json.dumps({'metricas': {'x': 1}}))\n")
    ferramentas = {"fake": {"comando": f"{sys.executable} {script}", "interpreta_saida": "json"}}

    resultado, eventos = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    item = resultado["resultados"][0]
    assert item["aprovado"] is False
    assert "json sem 'aprovado'" in item["motivo"]
    assert any(e["evento"] == "ferramenta.saida_invalida" for e in eventos)


def test_metricas_json_chegam_em_no_dependente(tmp_path):
    script = _script(
        tmp_path,
        "json_ok.py",
        "import json\nprint(json.dumps({'aprovado': True, 'metricas': {'tensao_max_mpa': 112}, 'motivo': ''}))\n",
    )
    spec = _spec(_tool_sub("fake"))
    spec["padrao"] = "grafo_dependencias"
    spec["subagentes"][0]["id"] = "simulador"
    spec["subagentes"].append({
        "id": "relator",
        "papel": "executor",
        "objetivo": "Relatar métricas",
        "entradas": {},
        "resultado_esperado": "Relatório",
        "rubrica": ["usa métricas"],
        "depende_de": ["simulador"],
    })
    ferramentas = {"fake": {"comando": f"{sys.executable} {script}", "interpreta_saida": "json"}}
    prompts = {}

    def roteador(papel: str, prompt: str):
        if papel == "executor":
            prompts["relator"] = prompt
            return "RELATÓRIO"
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
        politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "prosseguir"}),
        workspace_base=tmp_path / "runs",
        ferramentas=ferramentas,
        ferramentas_permitidas=[sys.executable],
        command_runner=RunnerFake(),
    )
    resultado = grafo.invoke({"spec": spec}, {"configurable": {"thread_id": "metricas-dep"}})

    assert resultado["resultados"][0]["metricas"] == {"tensao_max_mpa": 112}
    assert "Métricas:" in prompts["relator"]
    assert '"tensao_max_mpa": 112' in prompts["relator"]


def test_ferramenta_nao_registrada_ou_executavel_ausente_falha_explicita(tmp_path):
    resultado_sem_registro, eventos_sem_registro = _rodar(tmp_path, _spec(_tool_sub("sumida")), {})
    ferramentas = {"fake": {"comando": "executavel-que-nao-existe-xyz", "interpreta_saida": "exit_code"}}
    resultado_sem_exec, eventos_sem_exec = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    assert resultado_sem_registro["resultados"][0]["aprovado"] is False
    assert "não registrada" in resultado_sem_registro["resultados"][0]["motivo"]
    assert any(e["evento"] == "ferramenta.indisponivel" for e in eventos_sem_registro)
    assert resultado_sem_exec["resultados"][0]["aprovado"] is False
    assert "executável não permitido" in resultado_sem_exec["resultados"][0]["motivo"]
    assert any(e["evento"] == "ferramenta.indisponivel" for e in eventos_sem_exec)


def test_ferramenta_bloqueia_executavel_fora_da_allowlist_sem_subprocess(tmp_path, monkeypatch):
    def subprocess_proibido(*args, **kwargs):
        raise AssertionError("subprocess.run não deveria ser chamado")

    monkeypatch.setattr(RunnerFake, "run", subprocess_proibido)
    ferramentas = {"fake": {"comando": "bash -c 'echo nao-roda'", "interpreta_saida": "exit_code"}}

    resultado, eventos = _rodar(
        tmp_path,
        _spec(_tool_sub()),
        ferramentas,
        ferramentas_permitidas=["python3"],
    )

    item = resultado["resultados"][0]
    assert item["aprovado"] is False
    assert item["motivo"] == "executável não permitido: bash"
    assert any(
        e["evento"] == "ferramenta.indisponivel"
        and e["motivo"] == "executável não permitido: bash"
        for e in eventos
    )


def test_ferramenta_allowlist_permite_executavel_configurado(tmp_path):
    script = _script(tmp_path, "ok.py", "print('ok')\n")
    ferramentas = {"fake": {"comando": f"{sys.executable} {script}", "interpreta_saida": "exit_code"}}

    resultado, _ = _rodar(
        tmp_path,
        _spec(_tool_sub()),
        ferramentas,
        ferramentas_permitidas=[sys.executable],
    )

    assert resultado["resultados"][0]["aprovado"] is True
    assert resultado["resultados"][0]["saida"] == "ok"


def test_ferramenta_allowlist_ausente_falha_fechado(tmp_path):
    script = _script(tmp_path, "ok.py", "print('ok')\n")
    ferramentas = {"fake": {"comando": f"{sys.executable} {script}", "interpreta_saida": "exit_code"}}

    resultado, _ = _rodar(
        tmp_path, _spec(_tool_sub()), ferramentas, ferramentas_permitidas=None
    )

    assert resultado["resultados"][0]["aprovado"] is False
    assert "executável não permitido" in resultado["resultados"][0]["motivo"]


def test_cli_propaga_ferramentas_permitidas_da_config(tmp_path, monkeypatch):
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_spec(_tool_sub())), encoding="utf-8")
    cfg_path = tmp_path / "modelos.json"
    cfg_path.write_text(json.dumps({"ferramentas_permitidas": ["python3"]}), encoding="utf-8")
    capturado = {}

    class LogFake:
        def __init__(self, caminho):
            self.caminho = caminho

        def fechar(self):
            pass

    class GrafoFake:
        def invoke(self, entrada, config):
            return {"resposta_final": "ok"}

    def construir_fake(*args, **kwargs):
        capturado["ferramentas_permitidas"] = kwargs.get("ferramentas_permitidas")
        return GrafoFake()

    monkeypatch.setattr(sys, "argv", ["motor", "--modelos", str(cfg_path), "--spec", str(spec_path)])
    monkeypatch.setattr(cli, "LogEventos", LogFake)
    monkeypatch.setattr(cli, "construir_cliente", lambda *args, **kwargs: ClienteStub(lambda p, prompt: "ok"))
    monkeypatch.setattr(cli, "compor_orcamento_openai", lambda *_args, **_kwargs: SimpleNamespace(
        cliente=ClienteStub(lambda _p, _prompt: "ok"), repositorio=object(), fabrica=lambda *_: [],
    ))
    monkeypatch.setattr(cli, "construir_grafo", construir_fake)

    assert cli.main() == 0
    assert capturado["ferramentas_permitidas"] == ["python3"]


def test_ferramenta_que_escreve_arquivo_registra_ref(tmp_path):
    script = _script(
        tmp_path,
        "gera.py",
        "import pathlib, sys\npathlib.Path(sys.argv[1]).write_text('RELATORIO', encoding='utf-8')\n",
    )
    ferramentas = {
        "fake": {
            "comando": f"{sys.executable} {script} {{saida}}",
            "interpreta_saida": "exit_code",
            "produz": [{"nome": "relatorio.txt", "tipo": "txt", "de_placeholder": "saida"}],
        }
    }

    resultado, _ = _rodar(tmp_path, _spec(_tool_sub()), ferramentas)

    ref = resultado["resultados"][0]["artefatos"][0]
    assert resultado["resultados"][0]["aprovado"] is True
    assert ref["nome"] == "relatorio.txt"
    assert Path(ref["caminho"]).name == "check__relatorio.txt"
    assert Path(ref["caminho"]).read_text(encoding="utf-8") == "RELATORIO"


def test_ferramentas_de_registro_carrega_entidade_md(tmp_path):
    script = _script(tmp_path, "ok.py", "print('ok')\n")
    (tmp_path / "fake.md").write_text(
        "\n".join([
            "---",
            "tipo: ferramenta",
            "nome: fake",
            f"comando: \"{sys.executable} {script}\"",
            "interpreta_saida: exit_code",
            "ferramentas_permitidas: [python3, pytest]",
            "produz: [{\"nome\":\"saida.txt\",\"tipo\":\"txt\",\"de_placeholder\":\"saida\"}]",
            "---",
            "Ferramenta fake.",
        ]),
        encoding="utf-8",
    )

    ferramentas = ferramentas_de_registro(tmp_path)

    assert ferramentas["fake"]["interpreta_saida"] == "exit_code"
    assert ferramentas["fake"]["produz"][0]["nome"] == "saida.txt"
    assert ferramentas_permitidas_de_registro(tmp_path) == ["python3", "pytest"]
