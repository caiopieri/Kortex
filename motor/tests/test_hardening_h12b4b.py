from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from motor.modelos import ClienteRoteador, ClienteStub
from motor.openai_orcado import ClienteOpenAICusteado, MODELO, SnapshotFX
from motor.orcamento import (
    CotacaoTentativa,
    ErroOrcamento,
    IdentidadeTentativaCusteada,
    RepositorioOrcamento,
    ResultadoTentativa,
)


def _identidade(nome: str, tentativa: int = 1) -> IdentidadeTentativaCusteada:
    return IdentidadeTentativaCusteada(
        f"reserva-{nome}-{tentativa}", f"call-{nome}", nome, tentativa,
    )


def _openai(prompt: str, transporte):
    return ClienteOpenAICusteado(
        api_key="segredo", prompt=prompt, max_input_tokens=100,
        max_completion_tokens=20,
        fx=SnapshotFX("fx-1", 100, Decimal("5")), agora=100,
        fx_max_age_s=60, margem=Decimal("1.2"), timeout=10,
        transporte=transporte,
    )


def _roteador() -> ClienteRoteador:
    return ClienteRoteador(ClienteStub(lambda _papel, _prompt: "legado"))


def test_callsite_openai_reserva_antes_do_post_e_reconcilia_usage(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-1", "thread-1", Decimal("1"))
    observado: list[Decimal] = []

    def transporte(_url, _corpo, _headers, _timeout):
        observado.append(repo.sessao("run-1", "thread-1", Decimal("1")).reservado)
        corpo = (
            '{"model":"%s","choices":[{"message":{"content":"ok"}}],'
            '"usage":{"prompt_tokens":10,"completion_tokens":2,"total_tokens":12}}'
            % MODELO
        ).encode()
        return 200, {"x-request-id": "req-1"}, corpo

    resposta = _roteador().chamar_custeado(
        repo, sessao, [(_identidade("openai"), _openai("ola", transporte))],
    )

    assert resposta == "ok"
    assert observado and observado[0] > 0
    final = repo.sessao("run-1", "thread-1", Decimal("1"))
    assert final.reservado == 0
    assert final.gasto > 0


def test_budget_insuficiente_bloqueia_antes_do_post(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-2", "thread-2", Decimal("0.000001"))
    posts = 0

    def transporte(*_args):
        nonlocal posts
        posts += 1
        raise AssertionError("POST nao deveria ocorrer")

    assert _roteador().chamar_custeado(
        repo, sessao, [(_identidade("openai"), _openai("ola", transporte))],
    ) is None
    assert posts == 0


class _FakeCusteado:
    def __init__(self, texto: str | None) -> None:
        self.texto = texto
        self.chamadas = 0

    def cotar_tentativa(self) -> CotacaoTentativa:
        return CotacaoTentativa(Decimal("0.1"), "BRL", "price-1")

    def tentar_uma_vez(self) -> ResultadoTentativa:
        self.chamadas += 1
        return ResultadoTentativa(self.texto, Decimal("0.05"), "BRL", f"uso-{self.chamadas}")


def test_fallback_exige_nova_identidade_e_nova_reserva(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-3", "thread-3", Decimal("0.149999"))
    primeira, fallback = _FakeCusteado(None), _FakeCusteado("nao-deve-rodar")

    resposta = _roteador().chamar_custeado(repo, sessao, [
        (_identidade("primaria"), primeira),
        (_identidade("fallback"), fallback),
    ])

    assert resposta is None
    assert primeira.chamadas == 1
    assert fallback.chamadas == 0
    assert repo.sessao("run-3", "thread-3", Decimal("0.149999")).gasto == Decimal("0.05")


def test_fallback_valido_reconcilia_cada_tentativa_com_identidade_propria(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-3b", "thread-3b", Decimal("1"))
    primeira, fallback = _FakeCusteado(None), _FakeCusteado("ok")

    resposta = _roteador().chamar_custeado(repo, sessao, [
        (_identidade("primaria"), primeira),
        (_identidade("fallback"), fallback),
    ])

    assert resposta == "ok"
    assert primeira.chamadas == fallback.chamadas == 1
    final = repo.sessao("run-3b", "thread-3b", Decimal("1"))
    assert final.reservado == 0
    assert final.gasto == Decimal("0.10")


def test_erro_ambiguo_invalida_run_e_impede_fallback(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-4", "thread-4", Decimal("1"))
    fallback = _FakeCusteado("nao-deve-rodar")

    def ambiguo(*_args):
        return 500, {}, b"erro"

    assert _roteador().chamar_custeado(repo, sessao, [
        (_identidade("openai"), _openai("ola", ambiguo)),
        (_identidade("fallback"), fallback),
    ]) is None
    assert fallback.chamadas == 0
    assert repo.sessao("run-4", "thread-4", Decimal("1")).status == "INVALIDATED"


def test_config_invalida_falha_antes_de_qualquer_adaptador(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-5", "thread-5", Decimal("1"))
    valido = _FakeCusteado("nao-deve-rodar")
    invalido: Any = object()
    with pytest.raises(ErroOrcamento, match="adaptador custeado invalido"):
        _roteador().chamar_custeado(repo, sessao, [
            (_identidade("openai"), valido),
            (_identidade("invalido"), invalido),
        ])
    assert valido.chamadas == 0


def test_identidade_invalida_na_segunda_rota_falha_antes_da_primeira(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-6", "thread-6", Decimal("1"))
    valido = _FakeCusteado("nao-deve-rodar")
    identidade_invalida = IdentidadeTentativaCusteada("../reserva", "call", "rota", 1)
    with pytest.raises(ErroOrcamento, match="reservation_id invalido"):
        _roteador().chamar_custeado(repo, sessao, [
            (_identidade("openai"), valido),
            (identidade_invalida, valido),
        ])
    assert valido.chamadas == 0


@pytest.mark.parametrize("segunda", [
    IdentidadeTentativaCusteada("reserva-primeira-1", "call-segunda", "segunda", 1),
    IdentidadeTentativaCusteada("reserva-segunda-1", "call-primeira", "primeira", 1),
])
def test_colisao_de_ledger_na_segunda_rota_falha_antes_da_primeira(
    tmp_path: Path, segunda: IdentidadeTentativaCusteada,
) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-7", "thread-7", Decimal("1"))
    valido = _FakeCusteado("nao-deve-rodar")
    primeira = IdentidadeTentativaCusteada(
        "reserva-primeira-1", "call-primeira", "primeira", 1,
    )

    with pytest.raises(ErroOrcamento, match="tentativa custeada duplicada"):
        _roteador().chamar_custeado(repo, sessao, [(primeira, valido), (segunda, valido)])

    assert valido.chamadas == 0
