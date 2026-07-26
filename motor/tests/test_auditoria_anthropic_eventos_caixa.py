"""Reprodutores da auditoria Anthropic (grupos E — eventos — e A — caixa/orçamento).

ATENÇÃO: este arquivo é VERMELHO POR DESIGN. Cada teste asserta o comportamento
que os invariantes E1/E2/F1/F2 prometem e que o código atual **não** entrega.
Ver `docs/auditoria/ACHADOS-anthropic-eventos-caixa.md`. Nenhum código de
produção foi alterado por esta auditoria.
"""
from __future__ import annotations

import tempfile
import threading
import time
from operator import add
from pathlib import Path
from typing import Annotated, Any, cast

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from motor.caixa import CaixaFundador, LedgerCaixa, rodar_com_caixa
from motor.eventos import LogEventos
from tests.test_eventos_schema import _tipos_emitidos_em_codigo


# --------------------------------------------------------------------------
# A-01 (🔴) — decisão humana de um job é reaproveitada por outro job
# --------------------------------------------------------------------------

class _Estado(TypedDict):
    decisoes: Annotated[list[str], add]


class _LogFake:
    def evento(self, *args: Any, **kwargs: Any) -> None:
        pass


def _grafo_com_gate(saver: SqliteSaver, portao: str = "cobertura"):
    def gate(_estado: _Estado) -> _Estado:
        decisao = interrupt({"portao": portao, "opcoes": "prosseguir | abortar"})
        return {"decisoes": [f"gate:{decisao}"]}

    builder = StateGraph(_Estado)
    builder.add_node("gate", cast(Any, gate))
    builder.add_edge(START, "gate")
    builder.add_edge("gate", END)
    return builder.compile(checkpointer=saver)


def _responder_nota(caixa: CaixaFundador, portao: str, valor: str) -> None:
    for _ in range(1000):
        path = caixa._nota_path(portao)
        if path.exists() and "decisao: \n" in path.read_text():
            path.write_text(
                path.read_text().replace("decisao: \n", f"decisao: {valor}\n")
            )
            return
        time.sleep(0.005)


def test_decisao_de_um_job_nao_pode_ser_reusada_por_outro_job(tmp_path: Path) -> None:
    """F2: gates 'continuam independentes entre jobs'.

    A nota do fundador NÃO é namespaced por job (`PENDENTE — <portao>.md`) e o
    fallback `_decisao_arquivada` só é vetado por `tem_historico(job_id, portao)`,
    que é escopado por job. Resultado: job-b consome, sem nenhuma interação
    humana, a decisão arquivada que o humano deu para job-a.
    """
    caixa = CaixaFundador(tmp_path / "caixa", _LogFake(), timeout_s=3, poll_s=0)
    ledger = LedgerCaixa(tmp_path / "ledger.sqlite")
    try:
        with SqliteSaver.from_conn_string(str(tmp_path / "ckpt.sqlite")) as saver:
            grafo = _grafo_com_gate(saver)
            threading.Thread(
                target=_responder_nota, args=(caixa, "cobertura", "abortar"), daemon=True
            ).start()
            a = rodar_com_caixa(
                grafo, {"decisoes": []},
                {"configurable": {"thread_id": "job-a"}}, caixa, _LogFake(),
                ledger=ledger,
            )
            assert a["decisoes"] == ["gate:abortar"]

            # Ninguém responde nada para job-b: o gate tem que expirar (timeout),
            # nunca herdar a decisão de job-a.
            with pytest.raises(RuntimeError, match="não decidiu"):
                rodar_com_caixa(
                    grafo, {"decisoes": []},
                    {"configurable": {"thread_id": "job-b"}}, caixa, _LogFake(),
                    ledger=ledger,
                )
    finally:
        ledger.fechar()


# --------------------------------------------------------------------------
# A-02 (🔴) — rodar_com_caixa não renova o lease durante a retomada
# --------------------------------------------------------------------------

def test_retomada_longa_pela_cli_renova_o_lease(tmp_path: Path) -> None:
    """F1: 'claim/lease renovável'.

    `rodar_com_caixa` chama `ledger.consumir(...)` sem `lease_s` (caixa.py:647 e
    caixa.py:715), então a thread de renovação nunca sobe. Uma retomada que passe
    dos 30 s fixos do lease aplica o efeito no grafo e depois falha no ACK.
    """
    relogio = [1000.0]

    def montar(saver: SqliteSaver):
        def gate(_estado: _Estado) -> _Estado:
            decisao = interrupt({"portao": "gate", "opcoes": "prosseguir | abortar"})
            relogio[0] += 120.0  # retomada real leva mais que o lease de 30 s
            return {"decisoes": [f"gate:{decisao}"]}

        builder = StateGraph(_Estado)
        builder.add_node("gate", cast(Any, gate))
        builder.add_edge(START, "gate")
        builder.add_edge("gate", END)
        return builder.compile(checkpointer=saver)

    caixa = CaixaFundador(tmp_path / "caixa", _LogFake(), timeout_s=3, poll_s=0)
    ledger = LedgerCaixa(tmp_path / "ledger.sqlite", clock=lambda: relogio[0])
    try:
        with SqliteSaver.from_conn_string(str(tmp_path / "ckpt.sqlite")) as saver:
            grafo = montar(saver)
            threading.Thread(
                target=_responder_nota, args=(caixa, "gate", "prosseguir"), daemon=True
            ).start()
            resultado = rodar_com_caixa(
                grafo, {"decisoes": []},
                {"configurable": {"thread_id": "job-lento"}}, caixa, _LogFake(),
                ledger=ledger,
            )
            assert resultado["decisoes"] == ["gate:prosseguir"]
            estados = [
                dict(row)["lease_owner"]
                for row in ledger._conn.execute("SELECT lease_owner FROM caixa_outbox")
            ]
            assert estados == [":APPLIED:"], "efeito aplicado mas outbox não foi ACKed"
    finally:
        ledger.fechar()


# --------------------------------------------------------------------------
# E-01 (🟡) — sidecar de lock removido dá split-brain de writer
# --------------------------------------------------------------------------

def test_remocao_do_sidecar_nao_pode_permitir_segundo_writer(tmp_path: Path) -> None:
    """E2: 'writer único intra/interprocesso'.

    O inode do log é revalidado a cada escrita (`_validar_path_aberto`), mas o
    sidecar `.<nome>.lock` não é. Removido o sidecar (rotação de log, limpeza de
    dotfiles), um segundo writer abre no MESMO inode e a `seq` deixa de ser
    contígua/única.
    """
    path = tmp_path / "eventos.jsonl"
    primeiro = LogEventos(path)
    primeiro.evento("tarefa.concluida", missao="A1")
    (tmp_path / ".eventos.jsonl.lock").unlink()

    with pytest.raises(RuntimeError, match="writer ativo"):
        LogEventos(path)

    primeiro.fechar()


# --------------------------------------------------------------------------
# E-02 (🟡) — linha completa corrompida no meio torna o log ineditável
# --------------------------------------------------------------------------

def test_corrupcao_no_meio_do_log_deveria_ser_quarentenada(tmp_path: Path) -> None:
    """E2 promete 'recovery de tail com quarentena'.

    Só o sufixo após o último `\\n` é quarentenado. Uma linha completa corrompida
    (NULs/zero-fill pós-crash de ext4, edição manual) faz `LogEventos.__init__`
    levantar para sempre: o run perde a capacidade de emitir qualquer evento e
    nada é movido para quarentena.
    """
    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)
    log.evento("tarefa.concluida", missao="A1")
    log.fechar()
    with open(path, "ab") as arquivo:
        arquivo.write(b'{"t": 0.0, "seq": 2, "evento": "tarefa.conc\n')

    LogEventos(path).fechar()  # hoje: ValueError("linha 2 invalida no log")
    assert list(tmp_path.glob("*.quarentena")), "nada foi quarentenado"


# --------------------------------------------------------------------------
# E-03 (🟡) — guard anti-drift é cego para tipo de evento não literal
# --------------------------------------------------------------------------

def test_guard_anti_drift_enxerga_emissao_com_tipo_nao_literal() -> None:
    """E1: 'o conjunto de tipos de evento é fechado'.

    `_tipos_emitidos_em_codigo` só reconhece o 1º argumento quando ele é uma
    constante string. Qualquer emissão indireta (variável, f-string, constante de
    módulo) é invisível para o guard — inclusive `modelos.py:216`
    (`self.log.evento(tipo, **dados)`), a única emissão dinâmica hoje viva.
    """
    fonte = """
TIPO = "evento.novo"

def f(log):
    log.evento(TIPO, campo=1)
    log.evento(f"evento.{'derivado'}", campo=1)
"""
    assert _tipos_emitidos_em_codigo(fonte) != set(), "guard não enxerga emissão indireta"
