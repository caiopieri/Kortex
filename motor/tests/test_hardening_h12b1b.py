from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from multiprocessing import get_context
from pathlib import Path

import pytest

from motor.orcamento import ErroOrcamento, RepositorioOrcamento, ReservaOrcamento


def _reserva(nome: str, custo: str = "1") -> ReservaOrcamento:
    return ReservaOrcamento(nome, nome, "rota", 1, Decimal(custo), "p")


def _reservar(raiz: str, nome: str) -> bool:
    repo = RepositorioOrcamento(Path(raiz))
    try:
        return bool(repo.reservar(repo.sessao("run", "thread", Decimal("1")), _reserva(nome)))
    except ErroOrcamento:
        return False


def test_reconciliacao_libera_delta_e_replay(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2"))
    reserva = _reserva("r", "1")
    repo.reservar(sessao, reserva)
    assert repo.reconciliar(sessao, reserva, Decimal("0.4")).status == "RECONCILED"
    assert repo.reconciliar(sessao, reserva, Decimal("0.40")).status == "RECONCILED"
    with pytest.raises(ErroOrcamento, match="replay de reconciliacao divergente"):
        repo.reconciliar(sessao, reserva, Decimal("0.5"))
    atual = repo.sessao("run", "thread", Decimal("2"))
    assert (atual.gasto, atual.reservado, atual.status) == (Decimal("0.4"), Decimal("0"), "ACTIVE")


@pytest.mark.parametrize("custo", [None, True, Decimal("NaN"), Decimal("Infinity")])
def test_custo_invalido_conserva_reserva_e_invalida(tmp_path: Path, custo: object) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2"))
    reserva = _reserva("r")
    repo.reservar(sessao, reserva)
    assert repo.reconciliar(sessao, reserva, custo).status == "UNKNOWN_COST"
    atual = repo.sessao("run", "thread", Decimal("2"))
    assert (atual.gasto, atual.reservado, atual.status) == (Decimal("0"), Decimal("1"), "INVALIDATED")
    with pytest.raises(ErroOrcamento):
        repo.reservar(atual, _reserva("outra"))


def test_violacao_moeda_e_acima_do_maximo(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2"))
    reserva = _reserva("r")
    repo.reservar(sessao, reserva)
    assert repo.reconciliar(sessao, reserva, Decimal("3")).status == "CONTRACT_VIOLATED"
    atual = repo.sessao("run", "thread", Decimal("2"))
    assert (atual.gasto, atual.reservado, atual.status) == (Decimal("3"), Decimal("0"), "INVALIDATED")
    sessao2 = repo.sessao("run2", "thread", Decimal("2"))
    reserva2 = _reserva("r2")
    repo.reservar(sessao2, reserva2)
    assert repo.reconciliar(sessao2, reserva2, Decimal("1"), "USD").status == "CONTRACT_VIOLATED"
    assert repo.sessao("run2", "thread", Decimal("2")).reservado == Decimal("1")


def test_crash_restart_e_isolamento_por_run_thread(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    repo.reservar(repo.sessao("run", "a", Decimal("1")), _reserva("r"))
    reiniciado = RepositorioOrcamento(tmp_path)
    with pytest.raises(ErroOrcamento):
        reiniciado.reservar(reiniciado.sessao("run", "a", Decimal("1")), _reserva("r2"))
    assert reiniciado.reservar(reiniciado.sessao("run", "b", Decimal("1")), _reserva("b"))
    assert reiniciado.reservar(reiniciado.sessao("outra", "a", Decimal("1")), _reserva("o"))


def test_concorrencia_threads_e_processos_permite_uma_reserva(tmp_path: Path) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(lambda nome: _reservar(str(tmp_path), nome), ("t1", "t2"))) == 1
    raiz = str(tmp_path / "processos")
    with get_context("spawn").Pool(2) as pool:
        assert sum(pool.starmap(_reservar, ((raiz, "p1"), (raiz, "p2")))) == 1
