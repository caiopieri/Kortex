"""A costura de executor impõe os três invariantes pela FORMA, não pela confiança.

Um backend de harness é código de terceiro. O contrato não pode depender de ele se
comportar: tem que ser estruturalmente incapaz de violar o que importa.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from motor.costura_executor import (
    BackendExecutor,
    ErroCostura,
    PedidoExecucao,
    executar_com_costura,
    pedido_de,
)
from pathlib import Path

from motor.runner import CommandRequest, DenyCommandRunner


class _LogFalso:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    def evento(self, tipo: str, **dados: object) -> None:
        self.eventos.append((tipo, dict(dados)))


def _pedido(**kw: object) -> PedidoExecucao:
    base = dict(
        run_id="r1", no_id="A", papel="executor", fase="executor",
        prompt="faca algo", tentativa=1, teto=Decimal("10"),
    )
    base.update(kw)
    return pedido_de(**base)  # type: ignore[arg-type]


class _BackendBoto:
    nome = "boto"

    def executar(self, pedido: PedidoExecucao, emitir) -> str:
        emitir("ferramenta.executada", ferramenta="ls")
        return "saida do harness"


def test_backend_relata_e_nao_escreve_no_ledger_direto() -> None:
    """O backend recebe `emitir`, nunca o log. Ele relata; quem escreve é o motor."""
    log = _LogFalso()
    saida = executar_com_costura(_BackendBoto(), _pedido(), log)
    assert saida == "saida do harness"
    assert [tipo for tipo, _ in log.eventos] == ["ferramenta.executada"]


def test_evento_do_backend_carrega_a_coordenada_do_pedido() -> None:
    """Falha de backend não pode se apresentar como falha de outro nó (issues #12/#20)."""
    log = _LogFalso()
    executar_com_costura(_BackendBoto(), _pedido(papel="verifier", fase="verifier"), log)
    _, dados = log.eventos[0]
    assert dados["papel"] == "verifier"
    assert dados["fase"] == "verifier"


def test_execucao_e_negada_por_omissao() -> None:
    """Sem runner composto explicitamente, o backend não executa nada. Fail-closed."""
    pedido = _pedido()
    assert isinstance(pedido.command_runner, DenyCommandRunner)
    resultado = pedido.command_runner.run(CommandRequest(argv=("/bin/ls",), workspace=Path("/tmp"), timeout_s=1))
    assert resultado.erro == "runner_indisponivel"


def test_backend_nao_pode_alterar_o_envelope() -> None:
    """O teto é do motor. `frozen=True` não é decoração: é o invariante."""
    pedido = _pedido(teto=Decimal("5"))
    with pytest.raises(Exception):
        pedido.teto = Decimal("999")  # type: ignore[misc]


def test_envelope_invalido_reprova_antes_de_qualquer_efeito() -> None:
    for invalido in (Decimal("0"), Decimal("-1")):
        with pytest.raises(ErroCostura, match="envelope"):
            _pedido(teto=invalido)


def test_backend_sem_identidade_reprova() -> None:
    class _Anonimo:
        nome = ""

        def executar(self, pedido: PedidoExecucao, emitir) -> str:
            return "nao deveria rodar"

    with pytest.raises(ErroCostura, match="identidade"):
        executar_com_costura(_Anonimo(), _pedido(), _LogFalso())


def test_saida_nao_textual_reprova() -> None:
    class _Torto:
        nome = "torto"

        def executar(self, pedido: PedidoExecucao, emitir):
            return {"nao": "e texto"}

    with pytest.raises(ErroCostura, match="nao textual"):
        executar_com_costura(_Torto(), _pedido(), _LogFalso())


def test_backend_boto_satisfaz_o_protocolo() -> None:
    assert isinstance(_BackendBoto(), BackendExecutor)


def test_backend_nao_inventa_evento_fora_do_schema() -> None:
    """O backend é código de terceiro: ele não escolhe o vocabulário do ledger.

    Sem este guarda, um harness poderia furar o schema fechado em silêncio. O
    anti-drift de `test_eventos_schema.py` pegou este buraco no desenho original.
    """
    class _Inventivo:
        nome = "inventivo"

        def executar(self, pedido: PedidoExecucao, emitir) -> str:
            emitir("evento.que.nao.existe", x=1)
            return "nunca chega aqui"

    with pytest.raises(ErroCostura, match="fora do schema"):
        executar_com_costura(_Inventivo(), _pedido(), _LogFalso())
