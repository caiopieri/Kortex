"""Fronteira de composição para execução externa de comandos."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import selectors
import signal
import subprocess
import time
from pathlib import Path
from typing import Protocol
from uuid import uuid4

MAX_COMBINED_OUTPUT_BYTES = 1 << 20
MIN_TIMEOUT_S = 1
MAX_TIMEOUT_S = 300
TERM_GRACE_S = 2
_IMAGE_DIGEST = re.compile(
    r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?"
    r"(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)+@sha256:[0-9a-f]{64}\Z"
)
DOCKER_POLICY_VERSION = "h05b-docker-v1"


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


@dataclass(frozen=True)
class DockerSandboxEvidence:
    """Identidade observada no preflight; nao representa certificacao."""

    engine_version: str
    os_type: str
    adapter: str
    policy_version: str
    requested_image_digest: str
    effective_repo_digest: str


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
            raise ValueError("imagem deve usar referencia OCI completa fixada por digest sha256")
        if not executaveis or any(not item.startswith("/") for item in executaveis):
            raise ValueError("allowlist de executaveis absoluta obrigatoria")
        self.image_digest = image_digest
        self.executaveis = frozenset(executaveis)
        self.docker_bin = docker_bin

    def deployment_evidence(self) -> DockerSandboxEvidence:
        """Coleta a identidade efetiva sem alegar conformidade ou certificacao."""
        servidor = subprocess.run(
            [self.docker_bin, "version", "--format", "{{.Server.Version}}"],
            check=True, capture_output=True, text=True, timeout=5,
        )
        sistema = subprocess.run(
            [self.docker_bin, "info", "--format", "{{.OSType}}"],
            check=True, capture_output=True, text=True, timeout=5,
        )
        inspecao = subprocess.run(
            [self.docker_bin, "image", "inspect", "--format", "{{json .RepoDigests}}",
             self.image_digest],
            check=True, capture_output=True, text=True, timeout=5,
        )
        digests = json.loads(inspecao.stdout)
        digest_esperado = self.image_digest.rsplit("@", 1)[1]
        efetivos = [
            item for item in digests if isinstance(item, str)
            and item.rsplit("@", 1)[-1] == digest_esperado
        ] if isinstance(digests, list) else []
        versao = servidor.stdout.strip()
        os_type = sistema.stdout.strip()
        if not versao or os_type != "linux" or not efetivos:
            raise ValueError("preflight Docker nao corresponde ao deployment selado")
        return DockerSandboxEvidence(
            engine_version=versao,
            os_type=os_type,
            adapter=f"{type(self).__module__}.{type(self).__qualname__}",
            policy_version=DOCKER_POLICY_VERSION,
            requested_image_digest=self.image_digest,
            effective_repo_digest=efetivos[0],
        )

    def _preflight(self) -> str | None:
        try:
            self.deployment_evidence()
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as erro:
            return f"preflight Docker indisponivel: {type(erro).__name__}"
        except ValueError as erro:
            return str(erro)
        return None

    def _argv(self, request: CommandRequest) -> list[str]:
        if not request.argv or request.argv[0] not in self.executaveis:
            raise ValueError("executavel fora da allowlist do sandbox")
        if not request.workspace.is_absolute() or not request.workspace.is_dir():
            raise ValueError("workspace absoluto existente obrigatorio")
        if type(request.timeout_s) is not int or not MIN_TIMEOUT_S <= request.timeout_s <= MAX_TIMEOUT_S:
            raise ValueError("timeout invalido")
        if os.getuid() == 0:
            raise ValueError("host root nao pode definir usuario do sandbox")
        return [
            self.docker_bin, "run", "--init", "--pull", "never", "--network", "none",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "64",
            "--mount", f"type=bind,src={request.workspace},dst=/workspace,rw",
            "--workdir", "/workspace", "--user", f"{os.getuid()}:{os.getgid()}",
            "--entrypoint", request.argv[0], self.image_digest, *request.argv[1:],
        ]

    @staticmethod
    def _capture_limited(
        processo: subprocess.Popen[bytes], timeout_s: int,
    ) -> tuple[bytes, bytes, str | None]:
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        limite = time.monotonic() + timeout_s
        seletor = selectors.DefaultSelector()
        assert processo.stdout is not None and processo.stderr is not None
        seletor.register(processo.stdout, selectors.EVENT_READ, "stdout")
        seletor.register(processo.stderr, selectors.EVENT_READ, "stderr")
        try:
            while seletor.get_map():
                restante = limite - time.monotonic()
                if restante <= 0:
                    return bytes(buffers["stdout"]), bytes(buffers["stderr"]), "timeout"
                eventos = seletor.select(restante)
                if not eventos:
                    return bytes(buffers["stdout"]), bytes(buffers["stderr"]), "timeout"
                for chave, _ in eventos:
                    usado = len(buffers["stdout"]) + len(buffers["stderr"])
                    dados = os.read(chave.fd, min(65536, MAX_COMBINED_OUTPUT_BYTES - usado + 1))
                    if not dados:
                        seletor.unregister(chave.fileobj)
                        continue
                    disponivel = MAX_COMBINED_OUTPUT_BYTES - usado
                    buffers[chave.data].extend(dados[:disponivel])
                    if len(dados) > disponivel:
                        return bytes(buffers["stdout"]), bytes(buffers["stderr"]), "overflow"
            try:
                processo.wait(timeout=max(0, limite - time.monotonic()))
            except subprocess.TimeoutExpired:
                return bytes(buffers["stdout"]), bytes(buffers["stderr"]), "timeout"
            return bytes(buffers["stdout"]), bytes(buffers["stderr"]), None
        finally:
            seletor.close()

    @staticmethod
    def _terminate_tree(processo: subprocess.Popen[bytes]) -> bool:
        encerrado = True
        try:
            os.killpg(processo.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError:
            encerrado = False
        prazo = time.monotonic() + TERM_GRACE_S
        while time.monotonic() < prazo:
            try:
                os.killpg(processo.pid, 0)
            except ProcessLookupError:
                break
            except OSError:
                encerrado = False
                break
            time.sleep(0.01)
        try:
            os.killpg(processo.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            encerrado = False
        try:
            processo.wait(timeout=TERM_GRACE_S)
        except subprocess.TimeoutExpired:
            encerrado = False
        return encerrado

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
        resultado: CommandResult
        cleanup_erro: BaseException | None = None
        try:
            try:
                processo = subprocess.Popen(
                    comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                stdout, stderr, causa = self._capture_limited(processo, request.timeout_s)
                if causa is not None:
                    encerrado = self._terminate_tree(processo)
                    resultado = CommandResult(
                        stdout=stdout.decode(errors="replace"),
                        stderr=stderr.decode(errors="replace"),
                        erro=("termination_falhou" if not encerrado else
                              "output_overflow" if causa == "overflow" else "timeout"),
                        motivo=("encerramento da arvore falhou" if not encerrado else
                                "output combinado excedeu 1 MiB" if causa == "overflow"
                                else "timeout do sandbox"),
                        timed_out=causa == "timeout", truncated=causa == "overflow",
                    )
                else:
                    resultado = CommandResult(
                        returncode=processo.returncode,
                        stdout=stdout.decode(errors="replace"),
                        stderr=stderr.decode(errors="replace"),
                    )
            except OSError as erro:
                if "processo" in locals():
                    self._terminate_tree(processo)
                resultado = CommandResult(erro="sandbox_indisponivel", motivo=type(erro).__name__)
        finally:
            try:
                subprocess.run(
                    [self.docker_bin, "rm", "-f", nome], check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=TERM_GRACE_S,
                )
            except (OSError, subprocess.SubprocessError) as erro:
                cleanup_erro = erro
        if cleanup_erro is not None:
            return CommandResult(
                stdout=resultado.stdout, stderr=resultado.stderr,
                erro="cleanup_falhou", motivo=type(cleanup_erro).__name__,
                timed_out=resultado.timed_out, truncated=resultado.truncated,
            )
        return resultado
