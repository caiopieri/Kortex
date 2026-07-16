"""Studio permanece indisponível até possuir identidade, ledger e sink duráveis."""
from __future__ import annotations

from .orcamento import ErroOrcamento


def make_graph():
    raise ErroOrcamento("Studio sem sink monetario duravel; execucao proibida")
