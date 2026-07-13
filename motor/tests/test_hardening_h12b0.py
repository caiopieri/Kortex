from __future__ import annotations

import math
from typing import Any

import pytest

from motor.eventos import LogEventos
from motor.eventos_schema import EVENTOS_MONETARIOS, categoria_de, tipos, valido
from motor_painel.painel import parse_eventos


def _evento(tipo: str) -> dict[str, Any]:
    evento: dict[str, Any] = {
        "t": 0.0,
        "seq": 1,
        "evento": tipo,
        "run_id": "run-1",
        "thread_id": "thread-1",
        "call_id": "call-1",
        "rota": "openai:gpt-test",
        "tentativa": 1,
        "moeda": "BRL",
        "teto": "5.00",
        "gasto": "1.00",
        "reservado": "2.00",
    }
    if tipo == "custo.bloqueado":
        evento["motivo"] = "teto"
        return evento

    evento.update(
        reservation_id="reserva-1",
        maximo="1.00",
        pricing_version="precos-2026-07-12",
    )
    if tipo == "custo.reconciliado":
        evento.update(custo_real="0.60", delta_liberado="0.40")
    elif tipo == "custo.contrato_violado":
        evento.update(
            custo_real="6.00",
            moeda_recebida="BRL",
            motivo="custo_acima_maximo",
            gasto="6.00",
            reservado="0",
        )
    return evento


def _alterado(tipo: str, **mudancas: Any) -> dict[str, Any]:
    evento = _evento(tipo)
    evento.update(mudancas)
    return evento


def _payload(evento: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in evento.items() if k not in {"t", "seq", "evento"}}


def test_h12b0_schema_writer_e_painel_reconhecem_eventos(tmp_path) -> None:
    assert EVENTOS_MONETARIOS <= tipos()
    assert {categoria_de(tipo) for tipo in EVENTOS_MONETARIOS} == {"orcamento"}

    path = tmp_path / "eventos.jsonl"
    log = LogEventos(path)
    try:
        invalido = _evento("custo.reservado")
        invalido["maximo"] = True
        with pytest.raises(ValueError, match="fora do schema"):
            log.evento("custo.reservado", **_payload(invalido))
        assert path.read_bytes() == b""

        for tipo in sorted(EVENTOS_MONETARIOS):
            log.evento(tipo, **_payload(_evento(tipo)))
    finally:
        log.fechar()

    lidos = parse_eventos(path)
    assert [evento["seq"] for evento in lidos] == [1, 2, 3, 4]
    assert {evento["evento"] for evento in lidos} == EVENTOS_MONETARIOS


def test_h12b0_dominios_numericos_falham_fechado() -> None:
    maximos_hostis = [
        True, False, 1, 1.0, math.nan, math.inf, -math.inf,
        "0", "-0", "-1", "NaN", "Infinity", "1e0", "01", " 1",
    ]
    for valor in maximos_hostis:
        assert not valido(_alterado("custo.reservado", maximo=valor)), valor
    for valor in [True, math.nan, math.inf, "NaN", "Infinity", "-0", "-0.01"]:
        assert not valido(_alterado("custo.reconciliado", custo_real=valor)), valor
        assert not valido(_alterado("custo.contrato_violado", custo_real=valor)), valor
    for valor in [True, False, 0, -1, 1.0]:
        assert not valido(_alterado("custo.reservado", tentativa=valor)), valor


def test_h12b0_identidade_e_moeda_falham_fechado() -> None:
    hostis = [
        ("run_id", ""),
        ("thread_id", " thread"),
        ("call_id", "call\n2"),
        ("rota", []),
        ("reservation_id", ""),
        ("pricing_version", "v1\x00"),
        ("moeda", "USD"),
    ]
    for campo, valor in hostis:
        assert not valido(_alterado("custo.reservado", **{campo: valor})), campo


def test_h12b0_motivos_de_bloqueio_sao_enum_fechado() -> None:
    for motivo in ["sem_cotacao", "sem_adapter", "teto", "sessao_invalida"]:
        assert valido(_alterado("custo.bloqueado", motivo=motivo))
        assert not valido(_alterado("custo.bloqueado", motivo=f"{motivo}.outro"))


def test_h12b0_rejeita_correlacao_financeira_inconsistente() -> None:
    inconsistentes = [
        ("custo.reservado", {"reservado": "0.50"}),
        ("custo.reservado", {"gasto": "4.00", "reservado": "2.00"}),
        ("custo.reconciliado", {"delta_liberado": "0.39"}),
        ("custo.reconciliado", {"custo_real": "1.01", "delta_liberado": "0"}),
        ("custo.contrato_violado", {"custo_real": "1.00"}),
        ("custo.contrato_violado", {"gasto": "5.99"}),
        ("custo.contrato_violado", {"motivo": "moeda_divergente", "moeda_recebida": "BRL"}),
        ("custo.contrato_violado", {"motivo": "custo_invalido", "custo_real": "0"}),
    ]
    for tipo, mudancas in inconsistentes:
        assert not valido(_alterado(tipo, **mudancas)), (tipo, mudancas)


def test_h12b0_soma_exata_cobre_escalas_extremas() -> None:
    inteiro = "9" * 128
    fracao = "0." + "0" * 125 + "1"
    assert not valido(
        _alterado("custo.reservado", teto=inteiro, gasto=inteiro, reservado=fracao, maximo=fracao)
    )


def test_h12b0_violacoes_de_moeda_e_custo_invalido_sao_representaveis() -> None:
    assert valido(
        _alterado(
            "custo.contrato_violado",
            motivo="moeda_divergente",
            moeda_recebida="USD",
            custo_real="0.50",
            gasto="1.00",
            reservado="2.00",
        )
    )
    assert valido(
        _alterado(
            "custo.contrato_violado",
            motivo="custo_invalido",
            custo_real=None,
            gasto="1.00",
            reservado="2.00",
        )
    )


def test_h12b0_campo_extra_e_tick_legado_nao_ganham_autoridade() -> None:
    assert not valido(_alterado("custo.reservado", segredo="nao registrar"))
    tick = {
        "t": 0.0,
        "seq": 1,
        "evento": "custo.tick",
        "papel": "executor",
        "provedor": "stub",
        "modelo": "stub",
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2,
    }
    assert valido(tick)
    assert categoria_de("custo.tick") == "modelo"
    tick["gasto"] = "0"
    assert not valido(tick)
