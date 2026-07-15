from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, cast

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.modelos import ClienteModelo, ClienteRoteador, ClienteStub
from motor.orcamento import (
    CotacaoTentativa,
    ErroOrcamento,
    RepositorioOrcamento,
    ResultadoTentativa,
    RotaTentativaCusteada,
)
from motor.politica import PoliticaGates


class FakeLog:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict]] = []

    def evento(self, tipo: str, **dados) -> None:
        self.eventos.append((tipo, dados))


def _stub(resposta: str | None, provedor: str) -> ClienteStub:
    cliente = ClienteStub(lambda _papel, _prompt: resposta)
    cliente.provedor = provedor
    return cliente


@pytest.mark.parametrize("capacidades", [[""], [" codigo"], [1], "codigo"])
def test_h12a_capacidade_ausente_ou_hostil_nao_executa(capacidades) -> None:
    executor = _stub("INSEGURO", "executor")
    log = FakeLog()
    roteador = ClienteRoteador(
        padrao=executor,
        catalogo=[(executor, frozenset({"codigo"}), 1)],
        log=log,
    )

    resposta = roteador.chamar("executor", "p", capacidades=capacidades)

    assert resposta is None
    assert executor.chamadas == []
    assert log.eventos[-1][0] == "registro.sem_executor"


@pytest.mark.parametrize(
    "catalogo",
    [
        [],
        [(object(), frozenset({"codigo"}), 1)],
        [(_stub("x", "x"), {"codigo"}, 1)],
        [(_stub("x", "x"), frozenset({"codigo"}), True)],
    ],
)
def test_h12a_catalogo_ausente_ou_hostil_falha_fechado(catalogo) -> None:
    padrao = _stub("NAO DEVE RODAR", "padrao")
    roteador = ClienteRoteador(padrao=padrao, catalogo=catalogo)

    assert roteador.chamar("executor", "p", capacidades=["codigo"]) is None
    assert padrao.chamadas == []


def test_h12a_provedor_hostil_invalida_catalogo() -> None:
    executor = _stub("INSEGURO", "executor")
    executor.provedor = cast(Any, ["hostil"])
    roteador = ClienteRoteador(
        padrao=executor,
        catalogo=[(executor, frozenset({"codigo"}), 1)],
    )

    assert roteador.chamar("executor", "p", capacidades=["codigo"]) is None
    assert executor.chamadas == []


def test_h12a_rota_hostil_nao_chega_ao_catalogo() -> None:
    executor = _stub("INSEGURO", "executor")
    roteador = ClienteRoteador(
        padrao=executor,
        catalogo=[(executor, frozenset({"codigo"}), 1)],
    )

    assert roteador.chamar(
        "executor", "p", tier=cast(Any, []), capacidades=["codigo"]
    ) is None
    assert executor.chamadas == []


def test_h12a_lista_vazia_preserva_rota_legada() -> None:
    executor = _stub("LEGADO", "executor")
    roteador = ClienteRoteador(padrao=executor)

    assert roteador.chamar("executor", "p", capacidades=[]) == "LEGADO"
    assert len(executor.chamadas) == 1


@pytest.mark.parametrize("rota", ["pin", "tier"])
def test_h12a_pin_ou_tier_incapaz_nao_contorna_catalogo(rota: str) -> None:
    incapaz = _stub("INSEGURO", "incapaz")
    capaz = _stub("CAPAZ", "capaz")
    kwargs: dict[str, Any] = (
        {"pins": {"executor": incapaz}}
        if rota == "pin" else {"tiers": {"simples": incapaz}}
    )
    roteador = ClienteRoteador(
        padrao=capaz,
        catalogo=[
            (incapaz, frozenset({"redacao"}), 1),
            (capaz, frozenset({"codigo", "redacao"}), 2),
        ],
        **kwargs,
    )

    assert roteador.chamar("executor", "p", tier="simples", capacidades=["codigo"]) is None
    assert incapaz.chamadas == []
    assert capaz.chamadas == []


def test_h12a_fallback_mantem_todas_as_capacidades() -> None:
    primario = _stub(None, "primario")
    primario.provedor = None  # identidade de provedor ausente não permite repetir a própria rota
    incapaz = _stub("INSEGURO", "padrao")
    reserva = _stub("SEGURO", "reserva")
    roteador = ClienteRoteador(
        padrao=incapaz,
        tiers={"simples": primario},
        catalogo=[
            (primario, frozenset({"codigo", "pesquisa"}), 1),
            (incapaz, frozenset({"codigo"}), 2),
            (reserva, frozenset({"codigo", "pesquisa"}), 3),
        ],
    )

    assert roteador.chamar(
        "executor", "p", tier="simples", capacidades=["codigo", "pesquisa"]
    ) == "SEGURO"
    assert len(primario.chamadas) == 1
    assert incapaz.chamadas == []
    assert len(reserva.chamadas) == 1


def _spec_h12a() -> dict:
    return {
        "versao": "0.1",
        "padrao": "fan_out_sintese",
        "missao": {
            "id": "h12a",
            "objetivo": "validar rota runtime",
            "contexto": "",
            "criterios_cobertura": ["executor aprovado"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 1, "max_tentativas": 1},
        "subagentes": [{
            "id": "executor",
            "tipo": "modelo",
            "papel": "executor",
            "objetivo": "produzir resultado",
            "entradas": {},
            "resultado_esperado": "texto",
            "rubrica": ["entrega texto"],
            "capacidades_requeridas": ["codigo", "pesquisa"],
        }],
        "gates": [],
        "sintese": {"instrucao": "sintetize", "formato": "markdown"},
    }


@pytest.mark.parametrize("rota_valida", [True, False])
def test_h12a_grafo_executa_somente_rota_que_cobre_todas_capacidades(
    tmp_path, rota_valida: bool
) -> None:
    def juiz(papel: str, _prompt: str) -> str:
        if papel == "verifier":
            return json.dumps({"aprovado": True, "motivo": "ok"})
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(papel)

    padrao = ClienteStub(juiz)
    padrao.provedor = "juiz"
    incapaz = _stub("INSEGURO", "incapaz")
    capaz = _stub("RESULTADO", "capaz")
    log = LogEventos(tmp_path / "eventos.jsonl")
    try:
        catalogo: list[tuple[ClienteModelo, frozenset[str], int]] = [
            (incapaz, frozenset({"codigo"}), 1)
        ]
        if rota_valida:
            catalogo.append((capaz, frozenset({"codigo", "pesquisa"}), 2))
        roteador = ClienteRoteador(
            padrao=padrao,
            catalogo=catalogo,
            log=log,
        )

        class Tentativa:
            def __init__(self, papel: str, prompt: str, requisitos) -> None:
                self.papel, self.prompt, self.requisitos = papel, prompt, requisitos

            def cotar_tentativa(self) -> CotacaoTentativa:
                return CotacaoTentativa(Decimal("0.10"), "BRL", "teste-v1")

            def tentar_uma_vez(self) -> ResultadoTentativa:
                texto = roteador.chamar(
                    self.papel, self.prompt,
                    ferramentas=self.requisitos.ferramentas,
                    tier=self.requisitos.tier,
                    evitar=self.requisitos.evitar_provedor,
                    capacidades=(
                        list(self.requisitos.capacidades)
                        if self.requisitos.capacidades is not None else None
                    ),
                )
                return ResultadoTentativa(texto, Decimal("0.01"), "BRL", "teste-uso")

        grafo = construir_grafo(
            roteador,
            log,
            checkpointer=InMemorySaver(),
            politica=PoliticaGates(
                overrides={"plano": "prosseguir", "cobertura": "prosseguir"}
            ),
            repositorio_orcamento=RepositorioOrcamento(tmp_path / "orcamento"),
            fabrica_tentativas_orcadas=lambda papel, prompt, _tentativa, requisitos: [
                RotaTentativaCusteada(
                    f"teste:{papel}", f"teste-provider:{papel}",
                    Tentativa(papel, prompt, requisitos),
                )
            ],
        )

        resultado = grafo.invoke(
            {"spec": _spec_h12a(), "run_id": "h12a", "thread_id": "h12a"},
            {"configurable": {"thread_id": "h12a"}},
        )

        assert resultado["resultados"][0]["aprovado"] is rota_valida
        assert resultado["resultados"][0]["saida"] == ("RESULTADO" if rota_valida else "")
        assert incapaz.chamadas == []
        assert len(capaz.chamadas) == int(rota_valida)
    finally:
        log.fechar()


def test_h12a_grafo_bloqueia_cliente_direto_sem_enforcement(tmp_path) -> None:
    def direto(papel: str, _prompt: str) -> str:
        if papel == "executor":
            raise AssertionError("executor direto não pode rodar")
        if papel == "evaluator":
            return json.dumps({"aprovado": True, "lacunas": [], "nos_a_refazer": []})
        if papel == "synthesizer":
            return "FINAL"
        raise AssertionError(papel)

    cliente = ClienteStub(direto)
    cliente.roteamento_capacidades_runtime = False
    log = LogEventos(tmp_path / "eventos.jsonl")
    try:
        grafo = construir_grafo(
            cliente,
            log,
            checkpointer=InMemorySaver(),
            politica=PoliticaGates(
                overrides={"plano": "prosseguir", "cobertura": "prosseguir"}
            ),
        )

        resultado = grafo.invoke(
            {"spec": _spec_h12a()}, {"configurable": {"thread_id": "h12a-direto"}}
        )
        assert resultado["resultados"][0]["aprovado"] is False
        assert not any(papel == "executor" for papel, _ in cliente.chamadas)
    finally:
        log.fechar()


def test_construtor_certificado_nao_autoautoriza_cliente_stub(tmp_path) -> None:
    efeitos: list[str] = []
    cliente = ClienteStub(lambda papel, _prompt: efeitos.append(papel) or "INDEVIDO")
    log = LogEventos(tmp_path / "eventos-stub.jsonl")
    try:
        grafo = construir_grafo(cliente, log, checkpointer=InMemorySaver())
        with pytest.raises(ErroOrcamento, match="repositorio de orcamento ausente"):
            grafo.invoke(
                {
                    "missao_texto": "não execute",
                    "run_id": "stub-bloqueado",
                    "thread_id": "stub-bloqueado",
                },
                {"configurable": {"thread_id": "stub-bloqueado"}},
            )
        assert efeitos == []
    finally:
        log.fechar()
