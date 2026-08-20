"""Costura de executor: o lugar onde um harness de terceiro pode ser montado.

O motor **não é um harness** e não pretende virar um
(`docs/DECISAO-harness-e-costura-de-execucao.md`). Hoje o nó executor é uma chamada
de modelo que devolve texto: ele não lê arquivo, não roda código e não itera. Um
harness faz isso bem, é mantido por times grandes e comoditiza rápido — então ele é
**alugado**, não construído.

O que NÃO se aluga são três invariantes. Este módulo é o contrato que um backend
precisa satisfazer para ocupar o lugar do executor sem quebrá-los:

1. **envelope de orçamento** — o motor reserva antes do efeito; o backend roda livre
   DENTRO de um teto que ele não escolhe;
2. **roteamento de execução** — todo comando desce pelo `CommandRunner` certificado
   (`specs/001-hardening-producao/sandbox-conformance.md`);
3. **emissão de evidência** — o que aconteceu entra no ledger do motor.

A garantia não vem de confiar no backend: vem da **forma do contrato**. Ele recebe um
teto que não pode alterar, um `CommandRunner` que é o único caminho de execução que
lhe é dado, e um `emitir` — nunca o log. Backend não escreve no ledger; ele relata.

Espelha `CommandRunner` (`runner.py`): a implementação não é validada pelo tipo, é
**certificada contra documento**, nunca por auto-declaração
(`specs/001-hardening-producao/executor-conformance.md`).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Protocol, runtime_checkable

from .eventos_schema import ESQUEMA
from .runner import CommandRunner, DenyCommandRunner


class ErroCostura(Exception):
    """Violação do contrato da costura. Falha fechada, como todo guarda do motor."""


@dataclass(frozen=True)
class PedidoExecucao:
    """O que o motor entrega ao backend. Imutável de propósito.

    `teto` é o envelope já reservado. `None` significa medição monetária desligada
    explicitamente (`sem_contencao_monetaria`), nunca "sem limite por omissão".
    """

    run_id: str
    no_id: str
    papel: str
    fase: str
    prompt: str
    tentativa: int
    teto: Decimal | None
    command_runner: CommandRunner


Emitir = Callable[..., None]


@runtime_checkable
class BackendExecutor(Protocol):
    """Contrato a certificar; a implementação não é validada por este tipo."""

    nome: str

    def executar(self, pedido: PedidoExecucao, emitir: Emitir) -> str: ...


def _sem_execucao() -> CommandRunner:
    """Default do contrato é negar, igual ao do sandbox."""
    return DenyCommandRunner()


def pedido_de(
    *,
    run_id: str,
    no_id: str,
    papel: str,
    fase: str,
    prompt: str,
    tentativa: int,
    teto: Decimal | None,
    command_runner: CommandRunner | None = None,
) -> PedidoExecucao:
    """Monta o pedido com os guardas do contrato aplicados antes de qualquer efeito."""
    if not isinstance(run_id, str) or not run_id:
        raise ErroCostura("identidade da execucao ausente")
    if not isinstance(no_id, str) or not no_id:
        raise ErroCostura("no da execucao ausente")
    if teto is not None and (not isinstance(teto, Decimal) or teto <= 0):
        raise ErroCostura("envelope de orcamento invalido")
    return PedidoExecucao(
        run_id=run_id,
        no_id=no_id,
        papel=papel,
        fase=fase,
        prompt=prompt,
        tentativa=tentativa,
        teto=teto,
        command_runner=command_runner if command_runner is not None else _sem_execucao(),
    )


def executar_com_costura(
    backend: BackendExecutor,
    pedido: PedidoExecucao,
    log: Any,
) -> str:
    """Roda o backend com os três invariantes impostos pela forma, não pela confiança.

    O backend recebe `emitir`, nunca o `log`: ele **relata**, não escreve. Cada evento
    dele carrega a coordenada do pedido, então uma falha no backend não pode se
    apresentar como falha de outro nó — o defeito que a issue #12/#20 consertou.
    """
    if not isinstance(pedido, PedidoExecucao):
        raise ErroCostura("pedido invalido")
    nome = getattr(backend, "nome", None)
    if not isinstance(nome, str) or not nome:
        raise ErroCostura("backend sem identidade")

    def _evento(tipo: str, **dados: object) -> None:
        # O nome `_evento` NAO e estetico: e a convencao que o guard
        # anti-drift de `test_eventos_schema.py` reconhece para emissao
        # dinamica legitima. Renomear quebra a varredura estatica.
        # O backend e codigo de terceiro: ele NAO escolhe o vocabulario do ledger.
        # Sem esta checagem, um harness poderia inventar tipo de evento e furar o
        # schema fechado em silencio -- exatamente o drift que o guard anti-drift de
        # `test_eventos_schema.py` existe para impedir. Ele pegou este buraco.
        if not isinstance(tipo, str) or tipo not in ESQUEMA:
            raise ErroCostura(f"evento fora do schema fechado: {tipo!r}")
        log.evento(
            tipo,
            **dados,
            papel=pedido.papel,
            fase=pedido.fase,
        )

    saida = backend.executar(pedido, _evento)
    if not isinstance(saida, str):
        raise ErroCostura("backend devolveu saida nao textual")
    return saida
