import json
import sys

import pytest

from motor.__main__ import main


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
