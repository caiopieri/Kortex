import sqlite3
from decimal import Decimal
from pathlib import Path

from motor.orcamento import (
    CotacaoTentativa,
    IdentidadeTentativaCusteada,
    RepositorioOrcamento,
    ReservaOrcamento,
    ResultadoTentativa,
    TentativaBloqueadaPreEfeito,
    TentativaReconciliada,
    TentativaTerminal,
    executar_tentativa_custeada,
)


def _identidade(nome: str) -> IdentidadeTentativaCusteada:
    return IdentidadeTentativaCusteada(f"res-{nome}", f"call-{nome}", "rota-fake", 1)


class FakeCusteado:
    def __init__(self, repo: RepositorioOrcamento, run: str, resposta: object, *, quote: object = None) -> None:
        self.repo, self.run, self.resposta = repo, run, resposta
        self.quote = CotacaoTentativa(Decimal("1"), "BRL", "price-v1") if quote is None else quote
        self.chamadas = 0
        self.reserva_antes_do_efeito = False

    def cotar_tentativa(self) -> CotacaoTentativa:
        if isinstance(self.quote, Exception):
            raise self.quote
        return self.quote  # type: ignore[return-value]

    def tentar_uma_vez(self) -> ResultadoTentativa:
        self.chamadas += 1
        with sqlite3.connect(self.repo.caminho(self.run)) as con:
            self.reserva_antes_do_efeito = con.execute(
                "SELECT count(*) FROM budget_reservation WHERE status='RESERVED'"
            ).fetchone()[0] == 1 and con.execute(
                "SELECT count(*) FROM budget_outbox WHERE tipo='custo.reservado'"
            ).fetchone()[0] == 1
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta  # type: ignore[return-value]


def test_reserva_commita_antes_de_um_unico_efeito_e_reconcilia_none(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("3"))
    fake = FakeCusteado(repo, "run", ResultadoTentativa(None, Decimal("0.4"), "BRL", "usage-1"))
    resultado = executar_tentativa_custeada(repo, sessao, _identidade("a"), fake)
    assert isinstance(resultado, TentativaReconciliada)
    assert resultado.resultado.texto is None
    assert (fake.chamadas, fake.reserva_antes_do_efeito) == (1, True)
    atual = repo.sessao("run", "thread", Decimal("3"))
    assert (atual.gasto, atual.reservado, atual.status) == (Decimal("0.4"), Decimal("0"), "ACTIVE")


def test_sem_adapter_ou_cotacao_invalida_bloqueia_sem_efeito(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("3"))
    assert isinstance(
        executar_tentativa_custeada(repo, sessao, _identidade("adapter"), object()),
        TentativaBloqueadaPreEfeito,
    )
    fake = FakeCusteado(repo, "run", ResultadoTentativa("nao roda", Decimal("0"), "BRL", "usage"), quote=object())
    assert isinstance(
        executar_tentativa_custeada(repo, sessao, _identidade("quote"), fake),
        TentativaBloqueadaPreEfeito,
    )
    assert fake.chamadas == 0
    assert [e.payload["motivo"] for e in repo.listar_pendentes("run")] == ["sem_adapter", "sem_cotacao"]


def test_replay_ambiguo_e_bloqueio_de_teto_nao_chamam_transporte(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("1"))
    identidade = _identidade("replay")
    reserva = ReservaOrcamento(identidade.reservation_id, identidade.call_id, identidade.route_id, 1, Decimal("1"), "price-v1")
    assert repo.reservar_exclusiva(sessao, reserva).status == "NOVA"
    replay = FakeCusteado(repo, "run", ResultadoTentativa("x", Decimal("0"), "BRL", "usage"))
    resultado_replay = executar_tentativa_custeada(repo, sessao, identidade, replay)
    assert isinstance(resultado_replay, TentativaTerminal)
    assert resultado_replay.status_reserva == "REPLAY_AMBIGUO" and replay.chamadas == 0
    teto = FakeCusteado(repo, "run", ResultadoTentativa("x", Decimal("0"), "BRL", "usage"))
    resultado_teto = executar_tentativa_custeada(repo, sessao, _identidade("teto"), teto)
    assert isinstance(resultado_teto, TentativaBloqueadaPreEfeito)
    assert resultado_teto.motivo == "teto" and teto.chamadas == 0


def test_excecao_ou_resultado_invalido_invalida_sem_retry(tmp_path: Path) -> None:
    for nome, resposta in (("erro", RuntimeError("segredo")), ("invalido", object())):
        repo = RepositorioOrcamento(tmp_path / nome)
        sessao = repo.sessao("run", "thread", Decimal("2"))
        fake = FakeCusteado(repo, "run", resposta)
        resultado = executar_tentativa_custeada(repo, sessao, _identidade(nome), fake)
        assert isinstance(resultado, TentativaTerminal)
        assert resultado.status_reserva == "UNKNOWN_COST"
        atual = repo.sessao("run", "thread", Decimal("2"))
        assert (fake.chamadas, atual.reservado, atual.status) == (1, Decimal("1"), "INVALIDATED")
        outra = FakeCusteado(repo, "run", ResultadoTentativa("x", Decimal("0"), "BRL", "usage"))
        bloqueada = executar_tentativa_custeada(
            repo, sessao, _identidade(f"{nome}-sessao-invalida"), outra,
        )
        assert isinstance(bloqueada, TentativaTerminal)
        assert bloqueada.status_reserva == "BLOQUEADA" and outra.chamadas == 0


def test_custo_acima_do_maximo_contabiliza_e_invalida(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("3"))
    fake = FakeCusteado(repo, "run", ResultadoTentativa("x", Decimal("2"), "BRL", "usage"))
    resultado = executar_tentativa_custeada(repo, sessao, _identidade("alto"), fake)
    assert isinstance(resultado, TentativaTerminal)
    assert resultado.status_reserva == "CONTRACT_VIOLATED"
    atual = repo.sessao("run", "thread", Decimal("3"))
    assert (fake.chamadas, atual.gasto, atual.reservado, atual.status) == (1, Decimal("2"), Decimal("0"), "INVALIDATED")
