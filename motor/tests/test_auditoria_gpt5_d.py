import json
import os
import shlex
import sys
import time
from pathlib import Path
from typing import Any, cast

import pytest

from motor.grafo import construir_grafo
from motor.runner import CommandResult

PYTHON = shlex.quote(sys.executable)

# Estes testes exigem que um comando REALMENTE execute. O default do motor é
# `DenyCommandRunner` (grafo.py: command_runner or DenyCommandRunner()), que
# nega tudo fail-closed — por desenho, enquanto o backend de sandbox do H05b
# não estiver certificado. Sem runner real eles não podem passar, e forçá-los a
# passar exigiria afrouxar o default seguro.
#
# Rode com MOTOR_RUNNER_CERTIFICADO=1 no ambiente onde há backend certificado
# (ver motor/specs/001-hardening-producao/sandbox-conformance.md e o harness de
# conformance Linux). Fora dele, ficam explicitamente pulados — nunca silenciados.
requer_runner_certificado = pytest.mark.skipif(
    os.environ.get("MOTOR_RUNNER_CERTIFICADO") != "1",
    reason="H05b: exige backend de sandbox certificado; default é DenyCommandRunner (fail-closed)",
)


class _Nulo:
    def chamar(self, *args: Any, **kwargs: Any) -> None:
        return None

    evento = chamar


def _rodar(
    workspace: Path,
    comando: str,
    entradas: dict[str, Any],
    allowlist: list[str] | None,
    timeout: Any = 2,
) -> dict[str, Any]:
    grafo = construir_grafo(
        cast(Any, _Nulo()), cast(Any, _Nulo()), ferramentas_permitidas=allowlist
    )
    sub = {
        "id": "validador",
        "tipo": "validador",
        "valida": "alvo",
        "validador": {"kind": "comando", "config": {"comando": comando, "timeout": timeout}},
        "entradas": entradas,
    }
    payload = {
        "sub": sub,
        "spec": {"missao": {}, "restricoes": {"max_tentativas": 1}},
        "deps": {"alvo": "resultado"},
        "workspace": workspace,
    }
    return grafo.nodes["subagente"].invoke(payload)["resultados"][0]


class _RunnerCaptura:
    """Runner que captura o `argv` montado e nunca executa nada.

    Permite provar a fronteira C4 (metacaractere fica em UM argv) sem depender
    do backend de sandbox do H05b: o que importa é o argv que o motor entrega
    ao runner, não o efeito de rodá-lo.
    """

    def __init__(self) -> None:
        self.requests: list[Any] = []

    def run(self, request: Any) -> CommandResult:
        self.requests.append(request)
        return CommandResult(returncode=0, stdout="", stderr="")


def _capturar_argv(
    workspace: Path, comando: str, entradas: dict[str, Any], allowlist: list[str]
) -> tuple[str, ...]:
    captura = _RunnerCaptura()
    grafo = construir_grafo(
        cast(Any, _Nulo()),
        cast(Any, _Nulo()),
        ferramentas_permitidas=allowlist,
        command_runner=cast(Any, captura),
    )
    sub = {
        "id": "validador",
        "tipo": "validador",
        "valida": "alvo",
        "validador": {"kind": "comando", "config": {"comando": comando, "timeout": 2}},
        "entradas": entradas,
    }
    grafo.nodes["subagente"].invoke(
        {
            "sub": sub,
            "spec": {"missao": {}, "restricoes": {"max_tentativas": 1}},
            "deps": {"alvo": "resultado"},
            "workspace": workspace,
        }
    )
    assert len(captura.requests) == 1, "esperado exatamente um comando entregue ao runner"
    return captura.requests[0].argv


@pytest.mark.parametrize(
    "valor",
    [
        "com espaco",
        "aspas 'simples' e \"duplas\"",
        "; touch shell-marker",
        "&& touch shell-marker",
        "linha1\nlinha2",
        "$(touch shell-marker)",
        "`touch shell-marker`",
        "| touch shell-marker",
    ],
)
def test_c4_metacaractere_vira_exatamente_um_argv(tmp_path: Path, valor: str) -> None:
    """C4 provado na fronteira, sem runner real.

    O template é dividido por `shlex.split` ANTES da substituição, e cada parte
    recebe `format_map` individualmente — então um valor com espaço, aspas ou
    metacaractere de shell nunca se re-divide em argumentos extras. Não há shell
    envolvido: o argv vai direto ao runner.
    """
    argv = _capturar_argv(
        tmp_path / "workspace",
        f"{PYTHON} -c codigo {{valor}}",
        {"valor": valor},
        [sys.executable],
    )
    assert argv[-1] == valor, "o valor deve chegar inteiro, em um único argv"
    # executável, "-c", "codigo", valor — e nada mais.
    assert len(argv) == 4, f"nenhum argumento extra pode nascer do valor: {argv!r}"


def _runner(caminho: Path, corpo: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
    caminho.chmod(0o700)


@pytest.mark.parametrize("resolucao", ["path", "absoluto", "symlink"])
def test_c1_allowlist_deve_fixar_identidade_do_executavel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resolucao: str
) -> None:
    confiavel = tmp_path / "confiavel" / "audit-runner"
    malicioso = tmp_path / "malicioso" / "audit-runner"
    marcador = tmp_path / "executado"
    _runner(confiavel, "exit 0")
    _runner(malicioso, 'printf comprometido > "$1"')
    if resolucao == "path":
        monkeypatch.setenv("PATH", str(malicioso.parent))
        candidato = malicioso.name
    elif resolucao == "symlink":
        link = tmp_path / "link" / malicioso.name
        link.parent.mkdir()
        link.symlink_to(malicioso)
        candidato = str(link)
    else:
        candidato = str(malicioso)
    resultado = _rodar(
        tmp_path / "workspace",
        f"{shlex.quote(candidato)} {{marcador}}",
        {"marcador": marcador},
        [str(confiavel)],
    )
    assert not resultado["aprovado"] and not marcador.exists()


def test_c1_sem_allowlist_deve_falhar_fechado(tmp_path: Path) -> None:
    executavel = tmp_path / "malicioso" / "sem-lista"
    marcador = tmp_path / "executado"
    _runner(executavel, 'printf comprometido > "$1"')
    resultado = _rodar(
        tmp_path / "workspace",
        f"{shlex.quote(str(executavel))} {{marcador}}",
        {"marcador": marcador},
        None,
    )
    assert not resultado["aprovado"] and not marcador.exists()


@pytest.mark.parametrize("forma", ["absoluto", "traversal"])
def test_c2_workspace_deve_impedir_leitura_externa(tmp_path: Path, forma: str) -> None:
    workspace = tmp_path / "run" / "artefatos"
    segredo = tmp_path / "fora" / "segredo.txt"
    segredo.parent.mkdir()
    segredo.write_text("segredo-da-run-vizinha", encoding="utf-8")
    caminho = str(segredo) if forma == "absoluto" else os.path.relpath(segredo, workspace)
    codigo = "from pathlib import Path;import sys;print(Path(sys.argv[1]).read_text())"
    resultado = _rodar(
        workspace,
        f"{PYTHON} -c {shlex.quote(codigo)} {{arquivo}}",
        {"arquivo": caminho},
        [sys.executable],
    )
    assert not resultado["aprovado"] and "segredo-da-run-vizinha" not in resultado["saida"]


def test_c2_subprocesso_nao_deve_herdar_segredo_do_ambiente(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUDITORIA_SEGREDO", "segredo-do-host")
    codigo = "import os;print(os.environ['AUDITORIA_SEGREDO'])"
    resultado = _rodar(
        tmp_path / "workspace",
        f"{PYTHON} -c {shlex.quote(codigo)}",
        {},
        [sys.executable],
    )
    assert not resultado["aprovado"] and "segredo-do-host" not in resultado["saida"]


@pytest.mark.parametrize("timeout", [None, "0.25", []])
def test_c3_timeout_invalido_deve_reprovar_sem_excecao(tmp_path: Path, timeout: Any) -> None:
    resultado = _rodar(
        tmp_path / "workspace", f"{PYTHON} -c pass", {}, [sys.executable], timeout
    )
    assert not resultado["aprovado"] and "timeout" in resultado["motivo"].casefold()


@requer_runner_certificado
def test_c3_timeout_deve_encerrar_processos_descendentes(tmp_path: Path) -> None:
    marcador, pai = tmp_path / "filho-sobreviveu", tmp_path / "pai.py"
    pai.write_text(
        "import subprocess,sys,time\n"
        "filho=\"import sys,time;from pathlib import Path;time.sleep(1.2);"
        "Path(sys.argv[1]).write_text('orfao')\"\n"
        "subprocess.Popen([sys.executable,'-c',filho,sys.argv[1]],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
        "time.sleep(10)\n",
        encoding="utf-8",
    )
    resultado = _rodar(
        tmp_path / "workspace",
        f"{PYTHON} {{script}} {{marcador}}",
        {"script": pai, "marcador": marcador},
        [sys.executable],
        1,
    )
    assert not resultado["aprovado"]
    assert resultado["motivo"] == "timeout ao executar comando"
    limite = time.monotonic() + 2.5
    while time.monotonic() < limite and not marcador.exists():
        time.sleep(0.05)
    assert not marcador.exists()


@requer_runner_certificado
def test_c3_stdout_capturado_deve_ser_limitado(tmp_path: Path) -> None:
    tamanho = 512_000
    codigo = f"import sys;sys.stdout.write('x'*{tamanho})"
    resultado = _rodar(
        tmp_path / "workspace",
        f"{PYTHON} -c {shlex.quote(codigo)}",
        {},
        [sys.executable],
    )
    evidencia = json.loads(resultado["saida"])["evidencia"]
    assert resultado["aprovado"]
    assert len(evidencia["saida"]) < tamanho


def test_c4_placeholder_nao_deve_injetar_opcao(tmp_path: Path) -> None:
    marcador = tmp_path / "injecao-de-opcao"
    codigo = "from pathlib import Path;import sys;Path(sys.argv[1]).write_text('executado')"
    resultado = _rodar(
        tmp_path / "workspace",
        f"{PYTHON} {{modo}} {shlex.quote(codigo)} {{marcador}}",
        {"modo": "-c", "marcador": marcador},
        [sys.executable],
    )
    assert not resultado["aprovado"] and not marcador.exists()


@requer_runner_certificado
@pytest.mark.parametrize(
    "valor",
    [
        "com espaco",
        "aspas 'simples' e \"duplas\"",
        "; touch shell-marker",
        "&& touch shell-marker",
        "linha1\nlinha2",
    ],
)
def test_c4_metacaracteres_ficam_em_um_unico_argv(tmp_path: Path, valor: str) -> None:
    workspace, codigo = tmp_path / "workspace", "import sys;sys.stdout.write(sys.argv[1])"
    resultado = _rodar(
        workspace, f"{PYTHON} -c {shlex.quote(codigo)} {{valor}}", {"valor": valor}, [sys.executable]
    )
    evidencia = json.loads(resultado["saida"])["evidencia"]
    assert resultado["aprovado"] and evidencia["saida"] == valor
    assert not (workspace / "shell-marker").exists()
