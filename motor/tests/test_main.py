import json
import sys
from pathlib import Path

import pytest

from motor.__main__ import main


def test_main_modelos_e_registro_combinados(tmp_path, monkeypatch):
    """(a) Combinado monta cliente da config + rotas do registro."""
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

    # Intercept construir_cliente to check arguments and stop execution
    calls = []
    def mock_construir_cliente(cfg_modelos, dir_registro, log=None):
        calls.append((cfg_modelos, dir_registro))
        raise SystemExit(99)  # Stop execution before graph

    monkeypatch.setattr("motor.__main__.construir_cliente", mock_construir_cliente)

    with pytest.raises(SystemExit) as exc:
        main()
    
    assert exc.value.code == 99
    assert len(calls) == 1
    passed_cfg, passed_reg = calls[0]
    
    # Assert cliente came from config (reg_dir passed as None to construir_cliente)
    assert passed_cfg == cfg
    assert passed_reg is None


def test_main_backward_compat_so_registro(tmp_path, monkeypatch):
    """(b) Backward-compat: --registro sozinho continua usando cliente do registro."""
    reg_dir = tmp_path / "registro"
    reg_dir.mkdir()
    (reg_dir / "rotas").mkdir()

    monkeypatch.setattr(sys, "argv", ["motor", "missao", "--registro", str(reg_dir)])

    calls = []
    def mock_construir_cliente(cfg_modelos, dir_registro, log=None):
        calls.append((cfg_modelos, dir_registro))
        raise SystemExit(99)

    monkeypatch.setattr("motor.__main__.construir_cliente", mock_construir_cliente)
    # Prevent global pins from interfering
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")

    with pytest.raises(SystemExit) as exc:
        main()
    
    assert exc.value.code == 99
    passed_cfg, passed_reg = calls[0]
    assert passed_cfg is None
    assert passed_reg == str(reg_dir)


def test_main_backward_compat_so_modelos(tmp_path, monkeypatch):
    """(b) Backward-compat: --modelos sozinho continua usando cliente da config."""
    cfg = {"provedores": {"codex": {"tipo": "codex"}}}
    cfg_file = tmp_path / "modelos.json"
    cfg_file.write_text(json.dumps(cfg))

    monkeypatch.setattr(sys, "argv", ["motor", "missao", "--modelos", str(cfg_file)])

    calls = []
    def mock_construir_cliente(cfg_modelos, dir_registro, log=None):
        calls.append((cfg_modelos, dir_registro))
        raise SystemExit(99)

    monkeypatch.setattr("motor.__main__.construir_cliente", mock_construir_cliente)
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path / "fakehome")

    with pytest.raises(SystemExit) as exc:
        main()
    
    assert exc.value.code == 99
    passed_cfg, passed_reg = calls[0]
    assert passed_cfg == cfg
    assert passed_reg is None


def test_main_global_pins_only_nao_sequestra_registro(tmp_path, monkeypatch):
    """(c) Global pins-only não sequestra --registro sozinho."""
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

    calls = []
    def mock_construir_cliente(cfg_modelos, dir_registro, log=None):
        calls.append((cfg_modelos, dir_registro))
        raise SystemExit(99)

    monkeypatch.setattr("motor.__main__.construir_cliente", mock_construir_cliente)

    with pytest.raises(SystemExit) as exc:
        main()
    
    assert exc.value.code == 99
    passed_cfg, passed_reg = calls[0]
    # cfg_modelos has the pins from global config
    assert "pins" in passed_cfg
    # but since it doesn't have "provedores", it should NOT hijack the client
    # so dir_registro must be passed to construir_cliente
    assert passed_reg == str(reg_dir)
