from decimal import Decimal
from pathlib import Path

import pytest

from motor.orcamento import CotacaoTentativa, ErroOrcamento, RepositorioOrcamento, ReservaOrcamento


def _reserva(nome: str = "r1", maximo: str = "1") -> ReservaOrcamento:
    return ReservaOrcamento(nome, "call", "rota", 1, Decimal(maximo), "price-v1")


def test_sessao_e_reserva_sao_duraveis_e_texto_decimal(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-1", "thread-1", Decimal("2"))
    repo.reservar(sessao, _reserva())
    caminho = repo.caminho("run-1")
    assert caminho.exists()
    import sqlite3
    with sqlite3.connect(caminho) as con:
        assert con.execute("SELECT teto,gasto,reservado,typeof(teto) FROM budget_session").fetchone() == ("2", "0", "1", "text")
        assert con.execute("SELECT status,maximo,real,typeof(maximo) FROM budget_reservation").fetchone() == ("RESERVED", "1", None, "text")


def test_replay_idempotente_e_replay_divergente_falha_fechado(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("2"))
    assert repo.reservar(sessao, _reserva()).status == "RESERVED"
    assert repo.reservar(sessao, _reserva()).status == "RESERVED"
    with pytest.raises(ErroOrcamento, match="replay divergente"):
        repo.reservar(sessao, _reserva("outro"))


def test_teto_e_decimal_hostil_falham_sem_nova_reserva(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("1"))
    repo.reservar(sessao, _reserva())
    with pytest.raises(ErroOrcamento, match="teto excedido"):
        repo.reservar(sessao, ReservaOrcamento("r2", "call2", "rota", 1, Decimal("0.01"), "p"))
    for valor in (True, Decimal("NaN"), Decimal("Infinity")):
        with pytest.raises(ErroOrcamento):
            CotacaoTentativa(valor, "BRL", "p")  # type: ignore[arg-type]


@pytest.mark.parametrize("valor", ["", " run", "run ", "../run", "/tmp/run", "a/b", "a\\b", "a\x00b", "C:run"])
def test_identidade_rejeita_path_hostil_antes_de_derivar(tmp_path: Path, valor: str) -> None:
    with pytest.raises(ErroOrcamento):
        RepositorioOrcamento(tmp_path).sessao(valor, "thread", Decimal("1"))


def test_consulta_de_existencia_nao_cria_ledger(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    assert repo.possui_ledger("ausente") is False
    assert not (tmp_path / "ausente").exists()
    repo.sessao("presente", "thread", Decimal("1"))
    assert repo.possui_ledger("presente") is True
