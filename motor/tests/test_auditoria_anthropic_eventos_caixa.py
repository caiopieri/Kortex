"""Reprodutores da auditoria Anthropic (grupos E — eventos — e A — caixa/orçamento).

ATENÇÃO: este arquivo é VERMELHO POR DESIGN. Cada teste asserta o comportamento
que os invariantes E1/E2/F1/F2 prometem e que o código atual **não** entrega.
Ver `docs/auditoria/ACHADOS-anthropic-eventos-caixa.md`. Nenhum código de
produção foi alterado por esta auditoria.
"""
from __future__ import annotations

import inspect
import os
import re
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

import motor.caixa as caixa_mod
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


def _responder_nota(
    caixa: CaixaFundador, portao: str, valor: str, job_id: str
) -> None:
    """Simula o humano respondendo a nota DAQUELE job.

    O `job_id` é obrigatório de propósito: a nota é escopada por job, e um
    harness que escrevesse na nota "do portão" sem dizer de qual job estaria
    reproduzindo justamente o defeito que este arquivo audita.

    A escrita é atômica (tmp + `os.replace`) porque a Caixa relê a nota em laço:
    escrever no lugar deixa o leitor pegar o arquivo pela metade e levantar
    "nota inválida" — uma corrida do harness, não do que se quer medir.
    """
    escopada = caixa.para_job(job_id)
    for _ in range(1000):
        path = escopada._nota_path(portao)
        try:
            texto = path.read_text(encoding="utf-8") if path.exists() else ""
        except (OSError, UnicodeError):
            texto = ""
        if "decisao: \n" in texto:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                texto.replace("decisao: \n", f"decisao: {valor}\n"), encoding="utf-8"
            )
            os.replace(tmp, path)
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
                target=_responder_nota, args=(caixa, "cobertura", "abortar", "job-a"), daemon=True
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

def test_retomada_longa_pela_cli_renova_o_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F1: 'claim/lease renovável'.

    O defeito auditado: `rodar_com_caixa` reivindicava com `lease_s=30` mas
    chamava `ledger.consumir(...)` **sem** `lease_s` (caixa.py:647 e 715). A
    thread de renovação só sobe quando o lease é declarado no `consumir`
    (caixa.py:372), então ela nunca subia — e uma retomada mais longa que a
    janela aplicava o efeito no grafo e falhava no ACK, deixando a linha da
    outbox reelegível (redelivery, dois consumers no mesmo job).

    Nota sobre o mecanismo: a versão original deste reprodutor usava um relógio
    falso que saltava 120 s de uma vez. Isso não podia passar nem com o fix, e
    não por causa do defeito: a thread de renovação dorme em **tempo real**
    (`parar_renovacao.wait(duracao / 3)`), então um relógio que salta sem tempo
    real passar torna a renovação impossível por construção. Aqui o relógio é
    real e o lease é encurtado, o que exercita a renovação de verdade: a
    retomada dura ~6x a janela do lease e precisa sobreviver.
    """
    monkeypatch.setattr(caixa_mod, "_LEASE_CLI_S", 0.3)  # renova a cada 0.1 s
    duracao_retomada = 0.6

    def montar(saver: SqliteSaver):
        def gate(_estado: _Estado) -> _Estado:
            decisao = interrupt({"portao": "gate", "opcoes": "prosseguir | abortar"})
            time.sleep(duracao_retomada)  # bem mais que a janela do lease
            return {"decisoes": [f"gate:{decisao}"]}

        builder = StateGraph(_Estado)
        builder.add_node("gate", cast(Any, gate))
        builder.add_edge(START, "gate")
        builder.add_edge("gate", END)
        return builder.compile(checkpointer=saver)

    caixa = CaixaFundador(tmp_path / "caixa", _LogFake(), timeout_s=3, poll_s=0)
    ledger = LedgerCaixa(tmp_path / "ledger.sqlite")  # relógio real
    try:
        with SqliteSaver.from_conn_string(str(tmp_path / "ckpt.sqlite")) as saver:
            grafo = montar(saver)
            threading.Thread(
                target=_responder_nota, args=(caixa, "gate", "prosseguir", "job-lento"), daemon=True
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


def test_claim_e_consumo_da_cli_declaram_o_mesmo_lease() -> None:
    """A causa raiz de A-02, travada estruturalmente.

    `claim` e `consumir` têm que concordar sobre o lease. Enquanto o valor era
    literal em cada chamada, dava para reivindicar com 30 s e consumir sem
    declarar nada — que foi exatamente o defeito. Este teste falha se alguém
    reintroduzir literal solto ou esquecer o `lease_s` no consumo.
    """
    fonte = inspect.getsource(caixa_mod.rodar_com_caixa)
    consumos = re.findall(r"consumir\((?:[^()]|\([^()]*\))*\)", fonte)
    assert consumos, "esperado ao menos uma chamada a consumir"
    for chamada in consumos:
        assert "lease_s" in chamada, f"consumir sem lease_s: {chamada!r}"
    assert "lease_s=30" not in fonte, "lease literal: use a constante _LEASE_CLI_S"


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
