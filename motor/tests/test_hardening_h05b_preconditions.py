import json
import os
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest

from tests.helpers_grafo import construir_grafo_teste as construir_grafo
from motor.runner import (
    DOCKER_POLICY_VERSION,
    MAX_COMBINED_OUTPUT_BYTES,
    CommandRequest,
    CommandResult,
    DockerSandboxRunner,
)


class _Nulo:
    def chamar(self, *args: Any, **kwargs: Any) -> None:
        return None

    evento = chamar


class _RunnerRegistro:
    def __init__(self) -> None:
        self.requests: list[CommandRequest] = []

    def run(self, request: CommandRequest) -> CommandResult:
        self.requests.append(request)
        return CommandResult(returncode=0)


def _rodar(tmp_path: Path, timeout: Any, runner: _RunnerRegistro) -> dict[str, Any]:
    grafo = construir_grafo(
        cast(Any, _Nulo()),
        cast(Any, _Nulo()),
        ferramentas_permitidas=[sys.executable],
        command_runner=runner,
    )
    sub = {
        "id": "validador",
        "tipo": "validador",
        "valida": "alvo",
        "validador": {
            "kind": "comando",
            "config": {
                "comando": f"{shlex.quote(sys.executable)} -c pass",
                "timeout": timeout,
            },
        },
        "entradas": {},
    }
    return grafo.nodes["subagente"].invoke(
        {
            "sub": sub,
            "spec": {"missao": {}, "restricoes": {"max_tentativas": 1}},
            "deps": {"alvo": "resultado"},
            "workspace": tmp_path,
        }
    )["resultados"][0]


@pytest.mark.parametrize("timeout", [None, True, False, 0, -1, 301, 1.0, "1", []])
def test_timeout_invalido_falha_fechado_antes_do_runner(tmp_path: Path, timeout: Any) -> None:
    runner = _RunnerRegistro()

    resultado = _rodar(tmp_path, timeout, runner)

    assert resultado["aprovado"] is False
    assert "timeout inválido" in resultado["motivo"]
    assert runner.requests == []


@pytest.mark.parametrize("timeout", [1, 300])
def test_limites_de_timeout_sao_delegados_ao_runner(tmp_path: Path, timeout: int) -> None:
    runner = _RunnerRegistro()

    resultado = _rodar(tmp_path, timeout, runner)

    assert resultado["aprovado"] is True
    assert runner.requests[0].timeout_s == timeout


def test_docker_runner_rejeita_digest_e_allowlist_invalidos() -> None:
    with pytest.raises(ValueError, match="digest"):
        DockerSandboxRunner("latest", ("/bin/echo",))
    with pytest.raises(ValueError, match="OCI"):
        DockerSandboxRunner("sha256:" + "a" * 64, ("/bin/echo",))
    with pytest.raises(ValueError, match="allowlist"):
        DockerSandboxRunner("docker.io/library/alpine@sha256:" + "a" * 64, ("echo",))


def test_docker_runner_preflight_falha_fechado_sem_daemon(tmp_path: Path, monkeypatch) -> None:
    runner = DockerSandboxRunner("docker.io/library/alpine@sha256:" + "a" * 64, ("/bin/echo",))
    monkeypatch.setattr(runner, "_preflight", lambda: "preflight Docker indisponivel")
    resultado = runner.run(CommandRequest(("/bin/echo", "ok"), tmp_path, 1))
    assert resultado.erro == "sandbox_indisponivel"


def test_docker_runner_constroi_policy_selada(tmp_path: Path) -> None:
    runner = DockerSandboxRunner("docker.io/library/alpine@sha256:" + "b" * 64, ("/bin/echo",))
    comando = runner._argv(CommandRequest(("/bin/echo", "ok"), tmp_path, 3))
    assert "--pull" in comando and comando[comando.index("--pull") + 1] == "never"
    assert "none" in comando and "--read-only" in comando
    assert "--cap-drop" in comando and "ALL" in comando
    assert "--security-opt" in comando and "no-new-privileges" in comando
    assert "--env" not in comando and "--tmpfs" not in comando and "sh" not in comando
    assert comando[comando.index("--user") + 1] == f"{os.getuid()}:{os.getgid()}"
    indice = comando.index("--entrypoint")
    assert comando[indice + 1] == "/bin/echo"
    assert comando[indice + 2:] == [runner.image_digest, "ok"]
    assert comando.count("/bin/echo") == 1


def test_docker_runner_rejeita_host_root_antes_do_daemon(tmp_path: Path, monkeypatch) -> None:
    imagem = "docker.io/library/alpine@sha256:" + "e" * 64
    monkeypatch.setattr("motor.runner.os.getuid", lambda: 0)

    resultado = DockerSandboxRunner(imagem, ("/bin/echo",)).run(
        CommandRequest(("/bin/echo", "ok"), tmp_path, 1)
    )

    assert resultado.erro == "request_invalido"
    assert "host root" in resultado.motivo


def test_docker_runner_preflight_produz_identidade_e_digest_efetivo(monkeypatch) -> None:
    imagem = "docker.io/library/alpine@sha256:" + "c" * 64
    respostas = iter([
        subprocess.CompletedProcess([], 0, stdout="29.0.0\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout="linux\n", stderr=""),
        subprocess.CompletedProcess(
            [], 0, stdout=f'["alpine@{imagem.rsplit("@", 1)[1]}"]\n', stderr="",
        ),
    ])
    monkeypatch.setattr("motor.runner.subprocess.run", lambda *_args, **_kwargs: next(respostas))

    runner = DockerSandboxRunner(imagem, ("/bin/echo",))
    evidencia = runner.deployment_evidence()

    assert evidencia.engine_version == "29.0.0"
    assert evidencia.os_type == "linux"
    assert evidencia.adapter == "motor.runner.DockerSandboxRunner"
    assert evidencia.policy_version == DOCKER_POLICY_VERSION
    assert evidencia.requested_image_digest == imagem
    assert evidencia.effective_repo_digest == f"alpine@{imagem.rsplit('@', 1)[1]}"


@pytest.mark.parametrize(("sistema", "digests"), [
    ("darwin", "[]"),
    ("linux", "[]"),
    ("linux", "null"),
])
def test_docker_runner_preflight_rejeita_deployment_divergente(
    monkeypatch, sistema: str, digests: str,
) -> None:
    imagem = "docker.io/library/alpine@sha256:" + "d" * 64
    respostas = iter([
        subprocess.CompletedProcess([], 0, stdout="29.0.0\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout=sistema + "\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout=digests + "\n", stderr=""),
    ])
    monkeypatch.setattr("motor.runner.subprocess.run", lambda *_args, **_kwargs: next(respostas))

    assert "deployment selado" in (
        DockerSandboxRunner(imagem, ("/bin/echo",))._preflight() or ""
    )


def _docker_falso(tmp_path: Path) -> tuple[Path, Path, Path]:
    marcador = tmp_path / "container-live"
    cleanup = tmp_path / "cleanup"
    pid_filho = tmp_path / "child-pid"
    argv_log = tmp_path / "docker-argv.json"
    executavel = tmp_path / "docker-falso"
    executavel.write_text(f"""#!{sys.executable}
import json, os, pathlib, signal, subprocess, sys, time
live = pathlib.Path({str(marcador)!r})
cleanup = pathlib.Path({str(cleanup)!r})
child_pid = pathlib.Path({str(pid_filho)!r})
argv_log = pathlib.Path({str(argv_log)!r})
if sys.argv[1] == 'rm':
    live.unlink(missing_ok=True)
    cleanup.write_text(' '.join(sys.argv[1:]))
    raise SystemExit(0)
argv_log.write_text(json.dumps(sys.argv[1:]))
live.write_text('live')
modo = sys.argv[-1]
if modo == 'ok':
    os.write(1, b'out')
    os.write(2, b'err')
    raise SystemExit(0)
if modo == 'limit':
    os.write(1, b'a' * ({MAX_COMBINED_OUTPUT_BYTES} // 2))
    os.write(2, b'b' * ({MAX_COMBINED_OUTPUT_BYTES} // 2))
    raise SystemExit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN)
filho = subprocess.Popen([
    sys.executable, '-c',
    'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)',
])
child_pid.write_text(str(filho.pid))
if modo == 'overflow':
    bloco = b'x' * 65536
    for _ in range(17):
        os.write(1, bloco)
time.sleep(60)
""")
    executavel.chmod(0o755)
    return executavel, marcador, pid_filho


def _runner_falso(tmp_path: Path, monkeypatch) -> tuple[DockerSandboxRunner, Path, Path]:
    executavel, marcador, pid_filho = _docker_falso(tmp_path)
    runner = DockerSandboxRunner(
        "docker.io/library/alpine@sha256:" + "f" * 64,
        ("/bin/echo",),
        str(executavel),
    )
    monkeypatch.setattr(runner, "_preflight", lambda: None)
    return runner, marcador, pid_filho


def _assert_sem_residuo(marcador: Path, pid_filho: Path) -> None:
    assert not marcador.exists()
    pid = int(pid_filho.read_text())
    for _ in range(100):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.01)
    os.kill(pid, signal.SIGKILL)
    pytest.fail(f"processo residual: {pid}")


def test_docker_runner_limita_output_e_remove_arvore_container(tmp_path: Path, monkeypatch) -> None:
    runner, marcador, pid_filho = _runner_falso(tmp_path, monkeypatch)

    resultado = runner.run(CommandRequest(("/bin/echo", "overflow"), tmp_path, 5))

    assert resultado.erro == "output_overflow"
    assert resultado.truncated is True
    assert len(resultado.stdout.encode()) + len(resultado.stderr.encode()) == MAX_COMBINED_OUTPUT_BYTES
    _assert_sem_residuo(marcador, pid_filho)


def test_docker_runner_aceita_limite_combinado_exato(tmp_path: Path, monkeypatch) -> None:
    runner, marcador, _ = _runner_falso(tmp_path, monkeypatch)

    resultado = runner.run(CommandRequest(("/bin/echo", "limit"), tmp_path, 5))

    assert resultado.returncode == 0 and resultado.truncated is False
    assert len(resultado.stdout.encode()) + len(resultado.stderr.encode()) == MAX_COMBINED_OUTPUT_BYTES
    assert not marcador.exists()


def test_docker_runner_timeout_remove_arvore_container(tmp_path: Path, monkeypatch) -> None:
    runner, marcador, pid_filho = _runner_falso(tmp_path, monkeypatch)

    resultado = runner.run(CommandRequest(("/bin/echo", "timeout"), tmp_path, 1))

    assert resultado.erro == "timeout" and resultado.timed_out is True
    _assert_sem_residuo(marcador, pid_filho)


def test_docker_runner_cleanup_explicito_tambem_no_sucesso(tmp_path: Path, monkeypatch) -> None:
    runner, marcador, _ = _runner_falso(tmp_path, monkeypatch)

    resultado = runner.run(CommandRequest(("/bin/echo", "ok"), tmp_path, 5))

    assert resultado.returncode == 0
    assert (resultado.stdout, resultado.stderr) == ("out", "err")
    assert not marcador.exists()
    assert (tmp_path / "cleanup").read_text().startswith("rm -f motor-sandbox-")
    argv = json.loads((tmp_path / "docker-argv.json").read_text())
    indice = argv.index("--entrypoint")
    assert argv[indice + 1:indice + 4] == ["/bin/echo", runner.image_digest, "ok"]
