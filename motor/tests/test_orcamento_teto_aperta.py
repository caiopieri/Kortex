"""O teto da sessão aperta, nunca afrouxa.

Descoberto rodando: o planner abre a sessão com o teto de bootstrap (a spec
ainda não existe) e todos os nós seguintes reabrem a MESMA sessão com o
`teto_custo` da spec. Sem o aperto, `teto divergente` derruba toda run custeada
logo depois do planner.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from motor.orcamento import ErroOrcamento, RepositorioOrcamento, ReservaOrcamento


def test_teto_aperta_do_bootstrap_para_o_da_spec(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    repo.sessao("run-1", "thread-1", Decimal("900"))
    assert repo.sessao("run-1", "thread-1", Decimal("2.0")).teto == Decimal("2.0")
    # o aperto é durável, não só o valor devolvido
    assert repo.sessao("run-1", "thread-1", Decimal("2.0")).teto == Decimal("2.0")


def test_teto_nao_afrouxa(tmp_path: Path) -> None:
    """Afrouxar contornaria a única contenção monetária do sistema."""
    repo = RepositorioOrcamento(tmp_path)
    repo.sessao("run-2", "thread-2", Decimal("2.0"))
    with pytest.raises(ErroOrcamento, match="teto divergente"):
        repo.sessao("run-2", "thread-2", Decimal("900"))


def test_teto_nao_aperta_abaixo_do_ja_comprometido(tmp_path: Path) -> None:
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run-3", "thread-3", Decimal("900"))
    repo.reservar(sessao, ReservaOrcamento("r1", "call1", "rota", 1, Decimal("10"), "p"))
    with pytest.raises(ErroOrcamento, match="abaixo do ja comprometido"):
        repo.sessao("run-3", "thread-3", Decimal("5"))
