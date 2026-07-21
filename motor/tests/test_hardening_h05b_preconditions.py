import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from tests.helpers_grafo import construir_grafo_teste as construir_grafo
from motor.runner import CommandRequest, CommandResult, DockerSandboxRunner


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


def test_docker_runner_rejeita_host_root_antes_do_daemon(tmp_path: Path, monkeypatch) -> None:
    imagem = "docker.io/library/alpine@sha256:" + "e" * 64
    monkeypatch.setattr("motor.runner.os.getuid", lambda: 0)

    resultado = DockerSandboxRunner(imagem, ("/bin/echo",)).run(
        CommandRequest(("/bin/echo", "ok"), tmp_path, 1)
    )

    assert resultado.erro == "request_invalido"
    assert "host root" in resultado.motivo


def test_docker_runner_preflight_exige_linux_e_digest_efetivo(monkeypatch) -> None:
    imagem = "docker.io/library/alpine@sha256:" + "c" * 64
    respostas = iter([
        subprocess.CompletedProcess([], 0, stdout="29.0.0\n", stderr=""),
        subprocess.CompletedProcess([], 0, stdout="linux\n", stderr=""),
        subprocess.CompletedProcess(
            [], 0, stdout=f'["alpine@{imagem.rsplit("@", 1)[1]}"]\n', stderr="",
        ),
    ])
    monkeypatch.setattr("motor.runner.subprocess.run", lambda *_args, **_kwargs: next(respostas))

    assert DockerSandboxRunner(imagem, ("/bin/echo",))._preflight() is None


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
