"""Fronteira de composição para execução externa de comandos."""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import signal
import subprocess
from pathlib import Path
from typing import Protocol
from uuid import uuid4

MAX_COMBINED_OUTPUT_BYTES = 1 << 20
MIN_TIMEOUT_S = 1
MAX_TIMEOUT_S = 300
TERM_GRACE_S = 2
_IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


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


class DockerSandboxRunner:
    """Backend Docker estrito; a conformidade de deployment continua externa."""

    def __init__(self, image_digest: str, executaveis: tuple[str, ...], docker_bin: str = "docker") -> None:
        if not _IMAGE_DIGEST.fullmatch(image_digest):
            raise ValueError("imagem deve ser referenciada por digest sha256")
        if not executaveis or any(not item.startswith("/") for item in executaveis):
            raise ValueError("allowlist de executaveis absoluta obrigatoria")
        self.image_digest = image_digest
        self.executaveis = frozenset(executaveis)
        self.docker_bin = docker_bin

    def _preflight(self) -> str | None:
        try:
            subprocess.run(
                [self.docker_bin, "version", "--format", "{{.Server.Version}}"],
                check=True, capture_output=True, text=True, timeout=5,
            )
            subprocess.run(
                [self.docker_bin, "image", "inspect", self.image_digest],
                check=True, capture_output=True, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as erro:
            return f"preflight Docker indisponivel: {type(erro).__name__}"
        return None

    def _argv(self, request: CommandRequest) -> list[str]:
        if not request.argv or request.argv[0] not in self.executaveis:
            raise ValueError("executavel fora da allowlist do sandbox")
        if not request.workspace.is_absolute() or not request.workspace.is_dir():
            raise ValueError("workspace absoluto existente obrigatorio")
        if type(request.timeout_s) is not int or not MIN_TIMEOUT_S <= request.timeout_s <= MAX_TIMEOUT_S:
            raise ValueError("timeout invalido")
        return [
            self.docker_bin, "run", "--rm", "--init", "--pull", "never", "--network", "none",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "64", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--mount", f"type=bind,src={request.workspace},dst=/workspace,rw",
            "--workdir", "/workspace", "--user", "65532:65532", self.image_digest,
            *request.argv,
        ]

    def run(self, request: CommandRequest) -> CommandResult:
        try:
            comando = self._argv(request)
        except ValueError as erro:
            return CommandResult(erro="request_invalido", motivo=str(erro))
        motivo = self._preflight()
        if motivo is not None:
            return CommandResult(erro="sandbox_indisponivel", motivo=motivo)
        nome = f"motor-sandbox-{uuid4().hex}"
        comando[comando.index("--read-only"):comando.index("--read-only")] = ["--name", nome]
        try:
            processo = subprocess.Popen(
                comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                start_new_session=True,
            )
            stdout, stderr = processo.communicate(timeout=request.timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(processo.pid, signal.SIGTERM)
            try:
                stdout, stderr = processo.communicate(timeout=TERM_GRACE_S)
            except subprocess.TimeoutExpired:
                os.killpg(processo.pid, signal.SIGKILL)
                stdout, stderr = processo.communicate()
            subprocess.run([self.docker_bin, "rm", "-f", nome], capture_output=True, timeout=TERM_GRACE_S)
            combinado = (stdout or b"") + (stderr or b"")
            return CommandResult(
                stdout=stdout.decode(errors="replace"), stderr=stderr.decode(errors="replace"),
                erro="timeout", motivo="timeout do sandbox", timed_out=True,
                truncated=len(combinado) > MAX_COMBINED_OUTPUT_BYTES,
            )
        except OSError as erro:
            return CommandResult(erro="sandbox_indisponivel", motivo=type(erro).__name__)
        combinado = stdout + stderr
        truncado = len(combinado) > MAX_COMBINED_OUTPUT_BYTES
        if truncado:
            stdout, stderr = combinado[:MAX_COMBINED_OUTPUT_BYTES], b""
        return CommandResult(
            returncode=processo.returncode,
            stdout=stdout.decode(errors="replace"), stderr=stderr.decode(errors="replace"),
            truncated=truncado,
        )
