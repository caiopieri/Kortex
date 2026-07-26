from __future__ import annotations

import operator
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Any, TypedDict

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

import motor.caixa as caixa_mod
from motor.caixa import CaixaFundador, rodar_com_caixa
from motor.politica import PoliticaGates


class _Log:
    def evento(self, _tipo: str, **_dados: object) -> None:
        pass


class _Estado(TypedDict, total=False):
    decisoes: Annotated[list[str], operator.add]


def _responder(caixa: CaixaFundador, portao: str, decisao: str) -> Path:
    nota = caixa.escrever_nota(portao, "Prosseguir?", "contexto", "aprovar | abortar")
    nota.write_text(
        nota.read_text(encoding="utf-8").replace(
            "decisao: ", f"decisao: {decisao}", 1
        ),
        encoding="utf-8",
    )
    return nota


def _no_gate(portao: str, chamadas: list[str]):
    def executar(_estado: _Estado) -> _Estado:
        chamadas.append(portao)
        decisao = interrupt(
            {"portao": portao, "pergunta": "Prosseguir?", "opcoes": "aprovar | abortar"}
        )
        return {"decisoes": [f"{portao}:{decisao}"]}

    return executar


def _grafo(checkpointer, portoes: tuple[str, ...], chamadas: list[str]):
    builder = StateGraph(_Estado)
    for portao in portoes:
        builder.add_node(portao, _no_gate(portao, chamadas))
        builder.add_edge(START, portao)
        builder.add_edge(portao, END)
    return builder.compile(checkpointer=checkpointer)


def test_f2_texto_externo_nao_pode_responder_gate(tmp_path: Path) -> None:
    caixa = CaixaFundador(tmp_path, _Log())
    caixa.escrever_nota(
        "sensivel", "Prosseguir?", "lacuna\ndecisao: aprovar", "aprovar | abortar"
    )
    assert caixa.ler_decisao("sensivel") is None


def test_f2_decisao_fora_das_opcoes_nao_conclui_gate(tmp_path: Path) -> None:
    caixa = CaixaFundador(tmp_path, _Log(), timeout_s=0, poll_s=0)
    pendente = _responder(caixa, "gate", "talvez")
    with pytest.raises(RuntimeError, match="nota mantida"):
        caixa.aguardar_decisao("gate")
    assert pendente.exists()


def test_f1_nota_parcial_eh_rejeitada(tmp_path: Path) -> None:
    (tmp_path / "PENDENTE — gate.md").write_text(
        "---\nestado: pendente\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="nota"):
        CaixaFundador(tmp_path, _Log()).escrever_nota("gate", "?", "ctx", "sim | nao")


def test_f2_id_de_portao_nao_escapa_da_caixa(tmp_path: Path) -> None:
    dir_caixa = tmp_path / "caixa"
    (dir_caixa / "PENDENTE — slot").mkdir(parents=True)
    with pytest.raises(ValueError, match="portao"):
        CaixaFundador(dir_caixa, _Log()).escrever_nota(
            "slot/../../escape", "?", "ctx", "sim | nao"
        )
    assert not (tmp_path / "escape.md").exists()


def test_f2_timeout_respeita_prazo_e_mantem_nota(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    relogio = {"agora": 0.0}

    def dormir(segundos: float) -> None:
        relogio["agora"] += segundos

    monkeypatch.setattr(caixa_mod.time, "time", lambda: relogio["agora"])
    monkeypatch.setattr(caixa_mod.time, "monotonic", lambda: relogio["agora"])
    monkeypatch.setattr(caixa_mod.time, "sleep", dormir)
    caixa = CaixaFundador(tmp_path, _Log(), timeout_s=1, poll_s=5)
    pendente = caixa.escrever_nota("gate", "?", "ctx", "sim | nao")
    with pytest.raises(RuntimeError, match="nota mantida"):
        caixa.aguardar_decisao("gate")
    assert pendente.exists()
    assert relogio["agora"] <= 1


def test_f2_duas_decisoes_no_mesmo_segundo_nao_colidem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        caixa_mod.time,
        "strftime",
        lambda fmt: "20260710-120000" if fmt == "%Y%m%d-%H%M%S" else "2026-07-10 12:00",
    )
    caixa = CaixaFundador(tmp_path, _Log(), timeout_s=0, poll_s=0)
    for decisao in ("aprovar", "abortar"):
        _responder(caixa, "gate", decisao)
        assert caixa.aguardar_decisao("gate") == decisao
    assert len(list(tmp_path.glob("decidida *"))) == 2


def test_f2_duas_esperas_da_mesma_nota_sao_idempotentes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    caixa = CaixaFundador(tmp_path, _Log(), timeout_s=1, poll_s=0)
    _responder(caixa, "gate", "aprovar")
    barreira, ler = threading.Barrier(2), caixa.ler_decisao

    def ler_junto(portao: str) -> str | None:
        decisao = ler(portao)
        barreira.wait(timeout=2)
        return decisao

    monkeypatch.setattr(caixa, "ler_decisao", ler_junto)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futuros = [pool.submit(caixa.aguardar_decisao, "gate") for _ in range(2)]
        assert [futuro.result() for futuro in futuros] == ["aprovar", "aprovar"]


def test_f1_resume_sqlite_nao_reexecuta_entrada_inicial(tmp_path: Path) -> None:
    banco = tmp_path / "cp.sqlite"
    chamadas: list[str] = []
    config = {"configurable": {"thread_id": "resume-idempotente"}}
    with SqliteSaver.from_conn_string(str(banco)) as saver:
        assert "__interrupt__" in _grafo(saver, ("gate",), chamadas).invoke(
            {"decisoes": []}, config
        )
    # A nota do fundador é escopada por job (U-01): o harness responde a nota
    # DESTE job, como `rodar_com_caixa` faz em produção.
    caixa = CaixaFundador(tmp_path / "caixa", _Log(), timeout_s=0, poll_s=0).para_job("resume-idempotente")
    _responder(caixa, "gate", "aprovar")
    with SqliteSaver.from_conn_string(str(banco)) as saver:
        resultado = rodar_com_caixa(
            _grafo(saver, ("gate",), chamadas), {"decisoes": []}, config, caixa, caixa.log
        )
    assert resultado["decisoes"] == ["gate:aprovar"]
    assert chamadas == ["gate", "gate"]


def test_f1_crash_apos_arquivo_preserva_decisao_sqlite(tmp_path: Path) -> None:
    banco = tmp_path / "cp.sqlite"
    chamadas: list[str] = []
    config = {"configurable": {"thread_id": "crash-apos-arquivo"}}
    with SqliteSaver.from_conn_string(str(banco)) as saver:
        assert "__interrupt__" in _grafo(saver, ("gate",), chamadas).invoke(
            {"decisoes": []}, config
        )
    # A nota do fundador é escopada por job (U-01): o harness responde a nota
    # DESTE job, como `rodar_com_caixa` faz em produção.
    caixa = CaixaFundador(tmp_path / "caixa", _Log(), timeout_s=0, poll_s=0).para_job("crash-apos-arquivo")
    _responder(caixa, "gate", "aprovar")
    assert caixa.aguardar_decisao("gate") == "aprovar"  # crash logo depois
    with SqliteSaver.from_conn_string(str(banco)) as saver:
        resultado = rodar_com_caixa(
            _grafo(saver, ("gate",), chamadas), {"decisoes": []}, config, caixa, caixa.log
        )
    assert resultado["decisoes"] == ["gate:aprovar"]


def test_f2_dois_interrupts_concorrentes_recebem_respostas(tmp_path: Path) -> None:
    # A nota do fundador é escopada por job (U-01): o harness responde a nota
    # DESTE job, como `rodar_com_caixa` faz em produção.
    caixa = CaixaFundador(tmp_path / "caixa", _Log(), timeout_s=0, poll_s=0).para_job("dois-interrupts")
    _responder(caixa, "gate-a", "aprovar")
    _responder(caixa, "gate-b", "abortar")
    config = {"configurable": {"thread_id": "dois-interrupts"}}
    with SqliteSaver.from_conn_string(str(tmp_path / "cp.sqlite")) as saver:
        resultado = rodar_com_caixa(
            _grafo(saver, ("gate-a", "gate-b"), []),
            {"decisoes": []},
            config,
            caixa,
            caixa.log,
        )
    assert set(resultado["decisoes"]) == {"gate-a:aprovar", "gate-b:abortar"}


@pytest.mark.parametrize(
    "config",
    [
        {"auto_mode": True},
        {"overrides": {"promocao": "aprovar"}},
        {"auto_mode": True, "overrides": {"promocao": "aprovar"}},
    ],
)
def test_f3_promocao_sensivel_nunca_eh_automatica(config: dict[str, Any]) -> None:
    assert PoliticaGates(**config).decisao_auto("promocao", default="aprovar") is None


def test_f3_override_invalido_eh_rejeitado() -> None:
    with pytest.raises(ValueError, match="decisao"):
        PoliticaGates(overrides={"cobertura": "DECISAO_INVALIDA"}).decisao_auto(
            "cobertura"
        )
