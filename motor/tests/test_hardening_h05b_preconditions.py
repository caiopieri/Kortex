import shlex
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from tests.helpers_grafo import construir_grafo_teste as construir_grafo
from motor.runner import CommandRequest, CommandResult


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
