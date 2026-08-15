"""Runner local estritamente test-only; não demonstra confinamento."""
from __future__ import annotations

import subprocess
from typing import Any

import pytest

import motor.grafo as modulo_grafo
from motor.modelos import ClienteStub
from motor.runner import CommandRequest, CommandResult


class RunnerFake:
    def run(self, request: CommandRequest) -> CommandResult:
        try:
            proc = subprocess.run(
                request.argv,
                capture_output=True,
                text=True,
                timeout=request.timeout_s,
                stdin=subprocess.DEVNULL,
                cwd=request.workspace,
            )
        except OSError:
            return CommandResult(
                erro="executavel_ausente",
                motivo=f"executável ausente: {request.argv[0]}",
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                erro="timeout", motivo="timeout ao executar comando", timed_out=True
            )
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)


class ClienteCorpusOrcado(ClienteStub):
    """Adapta clientes do corpus congelado ao stub custeado estritamente test-only."""

    def __init__(self, base: Any) -> None:
        self.base = base

    def __getattr__(self, nome: str) -> Any:
        return getattr(self.base, nome)

    def chamar(self, papel: str, prompt: str, **kwargs: Any) -> str | None:
        return self.base.chamar(papel, prompt, **kwargs)


@pytest.fixture(autouse=True)
def injetar_runner_fake(monkeypatch: pytest.MonkeyPatch, request: Any) -> None:
    """Permite ao corpus H04 congelado compor o fake sem alterar seus arquivos."""
    monkeypatch.setattr(modulo_grafo, "subprocess", subprocess, raising=False)
    construir = modulo_grafo.construir_grafo

    def construir_com_fake(*args: Any, **kwargs: Any) -> Any:
        kwargs["command_runner"] = RunnerFake()
        if args and "repositorio_orcamento" not in kwargs and not isinstance(args[0], ClienteStub):
            args = (ClienteCorpusOrcado(args[0]), *args[1:])
        return construir(*args, **kwargs)

    monkeypatch.setattr(modulo_grafo, "construir_grafo", construir_com_fake)
    if getattr(request.module, "construir_grafo", None) is construir:
        monkeypatch.setattr(request.module, "construir_grafo", construir_com_fake)
