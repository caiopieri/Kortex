import json
import sys
from types import SimpleNamespace

import pytest

from motor.__main__ import main
from motor.runner import CommandResult


def test_main_modelos_e_registro_sem_orcamento_falha_fechado(tmp_path, monkeypatch):
    cfg = {"provedores": {"codex": {"tipo": "codex"}}}
    cfg_file = tmp_path / "modelos.json"
    cfg_file.write_text(json.dumps(cfg))

    reg_dir = tmp_path / "registro"
    reg_dir.mkdir()
    (reg_dir / "rotas").mkdir()
    (reg_dir / "rotas" / "minharota.md").write_text("---\ntipo: rota\n---\n")

    # Mock arguments
    monkeypatch.setattr(sys, "argv", [
        "motor", "minha missão",
        "--modelos", str(cfg_file),
        "--registro", str(reg_dir),
    ])

    monkeypatch.setattr(
        "motor.__main__.construir_cliente",
        lambda *_args, **_kwargs: pytest.fail("cliente legado nao deve ser construido"),
    )
    assert main() == 1


def test_main_so_registro_sem_orcamento_falha_fechado(tmp_path, monkeypatch):
    reg_dir = tmp_path / "registro"
    reg_dir.mkdir()
    (reg_dir / "rotas").mkdir()

    monkeypatch.setattr(sys, "argv", ["motor", "missao", "--registro", str(reg_dir)])

    monkeypatch.setattr(
        "motor.__main__.construir_cliente",
        lambda *_args, **_kwargs: pytest.fail("cliente legado nao deve ser construido"),
    )
    # Prevent global pins from interfering
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")

    assert main() == 1


def test_main_so_modelos_legado_sem_orcamento_falha_fechado(tmp_path, monkeypatch):
    cfg = {"provedores": {"codex": {"tipo": "codex"}}}
    cfg_file = tmp_path / "modelos.json"
    cfg_file.write_text(json.dumps(cfg))

    monkeypatch.setattr(sys, "argv", ["motor", "missao", "--modelos", str(cfg_file)])

    monkeypatch.setattr(
        "motor.__main__.construir_cliente",
        lambda *_args, **_kwargs: pytest.fail("ClienteOpenAICompat nao deve ser construido"),
    )
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")

    assert main() == 1


def test_main_global_pins_sem_orcamento_falha_fechado(tmp_path, monkeypatch):
    reg_dir = tmp_path / "registro"
    reg_dir.mkdir()
    (reg_dir / "rotas").mkdir()

    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    motor_dir = fake_home / ".motor"
    motor_dir.mkdir()
    pins_file = motor_dir / "pins.json"
    pins_file.write_text(json.dumps({"pins": {"synthesizer": "oc/openai/gpt-4o"}}))

    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)
    monkeypatch.setattr(sys, "argv", ["motor", "missao", "--registro", str(reg_dir)])

    monkeypatch.setattr(
        "motor.__main__.construir_cliente",
        lambda *_args, **_kwargs: pytest.fail("cliente legado nao deve ser construido"),
    )
    assert main() == 1


def test_flag_desconhecida_nao_vira_texto_de_missao(capsys, monkeypatch):
    """Parser manual: o que sobra vira missão e é despachado ao planner.

    Descoberto rodando: `--help` nunca foi tratado, virou texto de missão e
    disparou uma run paga de verdade antes de qualquer erro aparecer.
    """
    monkeypatch.setattr(sys, "argv", ["motor", "missao", "--verbos"])
    assert main() == 2
    assert "opção desconhecida: --verbos" in capsys.readouterr().out


def test_help_imprime_uso_em_vez_de_gastar(capsys, monkeypatch):
    for flag in ("--help", "-h"):
        monkeypatch.setattr(sys, "argv", ["motor", flag])
        assert main() == 2
        assert "opção desconhecida" not in capsys.readouterr().out


def test_help_documenta_flag_sandbox(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["motor", "--help"])

    assert main() == 2
    assert "--sandbox" in capsys.readouterr().out


def test_spec_com_modulo_ausente_aborta_antes_da_composicao_de_modelos(
    tmp_path, capsys, monkeypatch
):
    """Sem a sonda, `pytest` ausente só era descoberto depois de gastar modelos."""
    spec = {
        "versao": "0.1", "padrao": "grafo_dependencias",
        "missao": {"id": "preflight", "objetivo": "provar pareamento", "contexto": "",
                    "criterios_cobertura": ["não gastar modelo"]},
        "restricoes": {"teto_custo": 1.0, "max_subagentes": 2, "max_tentativas": 1},
        "subagentes": [
            {"id": "executor", "tipo": "modelo", "papel": "executor", "objetivo": "gerar",
             "entradas": {}, "resultado_esperado": "saída", "rubrica": ["entrega"]},
            {"id": "prova", "tipo": "validador", "valida": "executor", "depende_de": ["executor"],
             "objetivo": "testar", "entradas": {}, "resultado_esperado": "exit code 0",
             "validador": {"kind": "comando", "config": {
                 "comando": "/usr/local/bin/python3 -m pytest", "modulos_python": ["pytest"],
             }}},
        ],
        "gates": [], "sintese": {"instrucao": "sintetize", "formato": "markdown"},
    }
    spec_file = tmp_path / "missao.json"
    spec_file.write_text(json.dumps(spec), encoding="utf-8")
    cfg_file = tmp_path / "modelos.json"
    cfg_file.write_text(json.dumps({"omniroute": {}}), encoding="utf-8")

    class RunnerComModuloAusente:
        def __init__(self) -> None:
            self.requests: list[tuple[str, str]] = []

        def importar_modulo_python(self, executavel: str, modulo: str) -> CommandResult:
            self.requests.append((executavel, modulo))
            return CommandResult(returncode=1, stderr="ModuleNotFoundError")

    runner = RunnerComModuloAusente()
    evidencia = SimpleNamespace(
        engine_version="29.7.2", os_type="linux", policy_version="teste",
        effective_repo_digest="localhost/test@sha256:" + "a" * 64,
    )
    monkeypatch.setattr("motor.__main__.compor_sandbox", lambda _caminho: (runner, evidencia))
    monkeypatch.setattr(
        "motor.__main__.compor_orcamento_omniroute",
        lambda *_args: pytest.fail("não pode compor modelos antes do preflight do sandbox"),
    )
    monkeypatch.setattr(sys, "argv", [
        "motor", "--spec", str(spec_file), "--modelos", str(cfg_file),
        "--sandbox", "exemplos/sandbox-python.json",
    ])

    assert main() == 2
    assert runner.requests == [("/usr/local/bin/python3", "pytest")]
    saida = capsys.readouterr().out
    assert "sandbox 'exemplos/sandbox-python.json'" in saida
    assert "módulo Python 'pytest'" in saida
