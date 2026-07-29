"""Fronteira de composição do sandbox: `compor_sandbox` e a flag `--sandbox`.

Existe porque o bloqueio real nunca foi o adapter -- ele estava pronto e testado.
O bloqueio era que NENHUM ponto de entrada o compunha: toda execução de produção
recebia DenyCommandRunner, então o motor jamais rodou o código que escreve. Um
adapter que ninguém instancia é código morto com aparência de garantia.
"""
from __future__ import annotations

import json

import pytest

from motor.runner import DenyCommandRunner, compor_sandbox


def _cfg(tmp_path, **over):
    dados = {
        "image_digest": "docker.io/library/python@sha256:" + "a" * 64,
        "executaveis": ["/usr/local/bin/python3"],
        **over,
    }
    caminho = tmp_path / "sandbox.json"
    caminho.write_text(json.dumps(dados), encoding="utf-8")
    return caminho


def test_deny_continua_sendo_o_default_sem_a_flag() -> None:
    """Sem `--sandbox`, nada executa. Isso é o default seguro, não um defeito:
    liberar execução por omissão é a falha que este projeto não pode ter."""
    from motor.runner import CommandRequest
    from pathlib import Path

    resultado = DenyCommandRunner().run(CommandRequest((), Path("/tmp"), 1))
    assert resultado.erro == "runner_indisponivel"


def test_tag_mutavel_e_recusada(tmp_path) -> None:
    """Imagem por tag pode ser trocada por baixo entre dois runs, e aí a
    evidência de deployment deixa de identificar o que rodou."""
    with pytest.raises(ValueError, match="digest sha256"):
        compor_sandbox(_cfg(tmp_path, image_digest="python:3.13-slim"))


def test_allowlist_vazia_ou_relativa_e_recusada(tmp_path) -> None:
    with pytest.raises(ValueError, match="allowlist"):
        compor_sandbox(_cfg(tmp_path, executaveis=[]))
    with pytest.raises(ValueError, match="allowlist"):
        compor_sandbox(_cfg(tmp_path, executaveis=["python3"]))


def test_chave_desconhecida_na_config_e_recusada(tmp_path) -> None:
    """Fail-closed em chave extra: `{"network": "host"}` ignorado em silêncio é
    exatamente como uma contenção deixa de existir sem ninguém notar."""
    with pytest.raises(ValueError, match="config de sandbox invalida"):
        compor_sandbox(_cfg(tmp_path, network="host"))


def test_preflight_falho_impede_a_composicao(tmp_path) -> None:
    """O digest do fixture não existe localmente, então o preflight falha.

    O importante é que ele LEVANTE: se `compor_sandbox` devolvesse o runner
    mesmo assim, a missão rodaria inteira, todo portão "aprovaria" o que ninguém
    executou, e o operador acreditaria que houve execução.

    Os três tipos cobrem os três jeitos de não haver sandbox: imagem ausente
    (`CalledProcessError`), binário `docker` ausente (`OSError`) e preflight que
    não corresponde ao selado (`ValueError`). A CLI captura os três.
    """
    import subprocess

    with pytest.raises((ValueError, OSError, subprocess.SubprocessError)):
        compor_sandbox(_cfg(tmp_path))


def test_cli_passa_o_runner_composto_para_o_grafo() -> None:
    """Regressão estrutural: o defeito era o argumento não chegar ao grafo.

    Um teste de comportamento aqui exigiria missão real com Docker; o que precisa
    ser travado é mais simples e é justamente o que faltava -- que a CLI repasse
    `command_runner` em TODOS os caminhos de construção (com e sem `--caixa`).
    """
    import inspect

    from motor import __main__ as cli

    fonte = inspect.getsource(cli.main)
    assert fonte.count("command_runner=command_runner") == 2, (
        "todo caminho de construir_grafo precisa repassar o runner; "
        "um caminho sem ele volta silenciosamente para DenyCommandRunner"
    )
    assert fonte.count("construir_grafo(") == 2
