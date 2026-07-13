from __future__ import annotations

import importlib.util
from pathlib import Path


def test_manifest_h00_eh_integro_e_reproduzivel() -> None:
    script = Path(__file__).parents[1] / "tools/validar_manifest_reprodutores.py"
    spec = importlib.util.spec_from_file_location("validar_manifest", script)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    assert modulo.validar() == []
