from decimal import Decimal, localcontext
from typing import Any

from motor.eventos_schema import valido
from motor_painel.painel import obter_runs


def _reserva(**mudancas: Any) -> dict[str, Any]:
    evento: dict[str, Any] = {
        "t": 0.0,
        "seq": 1,
        "evento": "custo.reservado",
        "run_id": "run-1",
        "thread_id": "thread-1",
        "call_id": "call-1",
        "rota": "rota-1",
        "tentativa": 1,
        "moeda": "BRL",
        "teto": "5.00",
        "gasto": "1.00",
        "reservado": "2.00",
        "reservation_id": "reserva-1",
        "maximo": "1.00",
        "pricing_version": "precos-v1",
    }
    evento.update(mudancas)
    return evento


def test_h12b0_rejeita_violacao_sem_contabilizar_custo_real() -> None:
    evento = _reserva(
        evento="custo.contrato_violado",
        gasto="0",
        reservado="0",
        custo_real="6.00",
        moeda_recebida="BRL",
        motivo="custo_acima_maximo",
    )

    assert not valido(evento)


def test_h12b0_rejeita_reserva_acima_do_teto_sem_arredondar() -> None:
    evento = _reserva(
        teto="1.00000000000000000000000000000",
        gasto="0.99999999999999999999999999995",
        reservado="0.00000000000000000000000000006",
        maximo="0.00000000000000000000000000006",
    )
    with localcontext() as contexto:
        contexto.prec = 128
        assert Decimal(evento["gasto"]) + Decimal(evento["reservado"]) > Decimal(evento["teto"])

    assert not valido(evento)


def test_h12b0_telemetria_de_tokens_nao_altera_projecao_monetaria() -> None:
    inicio = {
        "t": 0.0,
        "seq": 1,
        "evento": "spec.recebida",
        "missao": "run-1",
        "subagentes": 1,
    }
    uso = {
        "t": 0.1,
        "seq": 2,
        "evento": "modelo.uso",
        "papel": "executor",
        "provedor": "openai",
        "modelo": "gpt-4o",
        "prompt_tokens": 1_000,
        "completion_tokens": 1_000,
        "total_tokens": 2_000,
    }

    assert obter_runs([inicio, uso])[0]["custo"] == obter_runs([inicio])[0]["custo"]
