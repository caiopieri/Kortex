import json
from decimal import Decimal

import pytest

from motor.orcamento import (
    CotacaoTentativa,
    ErroOrcamento,
    IdentidadeTentativaCusteada,
    RepositorioOrcamento,
    ResultadoTentativa,
    TentativaBloqueadaPreEfeito,
    TentativaTerminal,
    executar_tentativa_custeada,
)


class FakeCliente:
    def __init__(self, quote=None, result=None):
        self.quote = quote
        self.result = result
        self.chamadas = 0

    def cotar_tentativa(self):
        if isinstance(self.quote, Exception):
            raise self.quote
        return self.quote

    def tentar_uma_vez(self):
        self.chamadas += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("moeda", "USD"),
        ("maximo", Decimal("1e128")),
        ("pricing_version", "invalida/version"),
    ],
)
def test_cotacao_adulterada_bloqueia_sem_efeito(tmp_path, campo, valor):
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("5.0"))
    identidade = IdentidadeTentativaCusteada("res-1", "call-1", "rota", 1)
    quote = CotacaoTentativa(Decimal("1.0"), "BRL", "price-v1")
    object.__setattr__(quote, campo, valor)
    fake = FakeCliente(quote=quote, result=object())

    assert isinstance(
        executar_tentativa_custeada(repo, sessao, identidade, fake),
        TentativaBloqueadaPreEfeito,
    )
    assert fake.chamadas == 0
    assert [evento.payload["motivo"] for evento in repo.listar_pendentes("run")] == [
        "sem_cotacao"
    ]


def test_descriptors_hostis_bloqueiam_sem_vazar_segredo(tmp_path):
    class CotacaoHostil:
        @property
        def cotar_tentativa(self):
            raise RuntimeError("SEGREDO_HOSTIL_DESC")

        def tentar_uma_vez(self):
            return ResultadoTentativa(None, Decimal("1.0"), "BRL", "ref")

    class TentativaHostil:
        def cotar_tentativa(self):
            return CotacaoTentativa(Decimal("1"), "BRL", "price-v1")

        @property
        def tentar_uma_vez(self):
            raise RuntimeError("SEGREDO_HOSTIL_DESC")

    for indice, cliente in enumerate((CotacaoHostil(), TentativaHostil()), start=1):
        repo = RepositorioOrcamento(tmp_path / str(indice))
        sessao = repo.sessao("run", "thread", Decimal("5"))
        identidade = IdentidadeTentativaCusteada(
            f"res-{indice}", f"call-{indice}", "rota", 1
        )
        assert isinstance(
            executar_tentativa_custeada(repo, sessao, identidade, cliente),
            TentativaBloqueadaPreEfeito,
        )
        bruto = json.dumps(repo.listar_pendentes("run")[0].payload)
        assert "SEGREDO_HOSTIL_DESC" not in bruto
        assert '"motivo": "sem_adapter"' in bruto


def test_resultado_adulterado_escala_gigante_invalida_sessao(tmp_path):
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("5.0"))
    identidade = IdentidadeTentativaCusteada("res-3", "call-3", "rota", 1)

    result = ResultadoTentativa(None, Decimal("1.0"), "BRL", "ref")
    object.__setattr__(result, "custo_real", Decimal("1e128"))

    fake = FakeCliente(
        quote=CotacaoTentativa(Decimal("2.0"), "BRL", "price-v1"), result=result
    )
    assert isinstance(
        executar_tentativa_custeada(repo, sessao, identidade, fake), TentativaTerminal,
    )
    sessao_atual = repo.sessao("run", "thread", Decimal("5.0"))
    assert (fake.chamadas, sessao_atual.reservado, sessao_atual.status) == (
        1,
        Decimal("2"),
        "INVALIDATED",
    )
    violacao = repo.listar_pendentes("run")[-1]
    assert (violacao.tipo, violacao.payload["motivo"], violacao.payload["custo_real"]) == (
        "custo.contrato_violado",
        "custo_invalido",
        None,
    )


@pytest.mark.parametrize(
    "identidade",
    [object(), IdentidadeTentativaCusteada("res", "call", "rota", True)],
)
def test_identidade_invalida_vira_erro_de_dominio_sem_evento(tmp_path, identidade):
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("5.0"))
    with pytest.raises(ErroOrcamento):
        executar_tentativa_custeada(repo, sessao, identidade, object())
    assert repo.listar_pendentes("run") == []


def test_quote_exception_segredo_nao_vaza(tmp_path):
    """(5) Excecao de cotacao com segredo nao deve aparecer no payload/outbox."""
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("5.0"))
    identidade = IdentidadeTentativaCusteada("res-5", "call-5", "rota", 1)

    fake = FakeCliente(quote=RuntimeError("API_KEY=sk_test_secret_12345"))
    executar_tentativa_custeada(repo, sessao, identidade, fake)

    pendentes = repo.listar_pendentes("run")
    assert len(pendentes) == 1
    bruto = json.dumps(pendentes[0].payload)
    assert "sk_test_secret" not in bruto
    assert "API_KEY" not in bruto


def test_replay_e_nova_tentativa_explicita(tmp_path):
    """(6) Replay nao chama o transporte de novo, mas nova tentativa com ID distinto chama mais uma vez."""
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("5.0"))

    identidade1 = IdentidadeTentativaCusteada("res-6", "call-6", "rota", 1)
    result = ResultadoTentativa(None, Decimal("1.0"), "BRL", "usage-ref")
    fake1 = FakeCliente(
        quote=CotacaoTentativa(Decimal("2.0"), "BRL", "price-v1"), result=result
    )

    executar_tentativa_custeada(repo, sessao, identidade1, fake1)
    assert fake1.chamadas == 1

    fake2 = FakeCliente(
        quote=CotacaoTentativa(Decimal("2.0"), "BRL", "price-v1"), result=result
    )
    replay = executar_tentativa_custeada(repo, sessao, identidade1, fake2)
    assert isinstance(replay, TentativaTerminal)
    assert replay.status_reserva == "REPLAY_FINALIZADO"
    assert fake2.chamadas == 0

    identidade2 = IdentidadeTentativaCusteada("res-7", "call-6", "rota", 2)
    fake3 = FakeCliente(
        quote=CotacaoTentativa(Decimal("2.0"), "BRL", "price-v1"), result=result
    )
    executar_tentativa_custeada(repo, sessao, identidade2, fake3)
    assert fake3.chamadas == 1
