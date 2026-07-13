"""Fronteira de composição para execução externa de comandos."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

MAX_COMBINED_OUTPUT_BYTES = 1 << 20
MIN_TIMEOUT_S = 1
MAX_TIMEOUT_S = 300
TERM_GRACE_S = 2


@dataclass(frozen=True)
class CommandRequest:
    argv: tuple[str, ...]
    workspace: Path
    timeout_s: int


@dataclass(frozen=True)
class CommandResult:
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    erro: str | None = None
    motivo: str = ""
    timed_out: bool = False
    truncated: bool = False


class CommandRunner(Protocol):
    """Contrato a certificar em H05b; sua implementação não é validada por este tipo."""

    def run(self, request: CommandRequest) -> CommandResult: ...


class DenyCommandRunner:
    """Default seguro: comando indisponível sem runner externo composto."""

    def run(self, request: CommandRequest) -> CommandResult:
        del request
        return CommandResult(
            erro="runner_indisponivel",
            motivo="runner externo de comando indisponível",
        )
