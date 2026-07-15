"""Infraestrutura offline de testes; nunca importar em código de produção."""
from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from motor.grafo import construir_grafo
from motor.modelos import ClienteStub
from motor.orcamento import (
    CotacaoTentativa,
    RepositorioOrcamento,
    RequisitosTentativaCusteada,
    ResultadoTentativa,
    RotaTentativaCusteada,
)
from motor.servico import GerenciadorJobs


def dependencias_stub(cliente: ClienteStub, raiz: Path | None = None) -> dict[str, Any]:
    repo = RepositorioOrcamento(raiz or Path(tempfile.mkdtemp(prefix="kortex-stub-")))

    class TentativaStub:
        def __init__(self, papel: str, prompt: str) -> None:
            self.papel, self.prompt = papel, prompt

        def cotar_tentativa(self) -> CotacaoTentativa:
            return CotacaoTentativa(Decimal("0.000001"), "BRL", "stub-offline-v1")

        def tentar_uma_vez(self) -> ResultadoTentativa:
            return ResultadoTentativa(
                cliente.chamar(self.papel, self.prompt),
                Decimal("0"), "BRL", "stub-offline-usage",
            )

    def fabricar(
        papel: str, prompt: str, _tentativa: int, _requisitos: RequisitosTentativaCusteada,
    ) -> list[RotaTentativaCusteada]:
        return [RotaTentativaCusteada(
            f"stub:{papel}", f"stub-provider:{papel}", TentativaStub(papel, prompt),
        )]

    return {"repositorio_orcamento": repo, "fabrica_tentativas_orcadas": fabricar}


def construir_grafo_teste(cliente: Any, log: Any, **kwargs: Any):
    """Compila Stub offline com custo fake somente quando não há deps explícitas."""
    repo = kwargs.get("repositorio_orcamento")
    fabrica = kwargs.get("fabrica_tentativas_orcadas")
    if (repo is None) != (fabrica is None):
        raise ValueError("repo e fabrica de teste devem ser fornecidos juntos")
    if repo is not None or not isinstance(cliente, ClienteStub):
        return construir_grafo(cliente, log, **kwargs)
    kwargs.update(dependencias_stub(cliente))
    return construir_grafo(cliente, log, **kwargs)


class GerenciadorJobsTeste(GerenciadorJobs):
    """Serviço offline que fornece deps fake explicitamente fora do pacote produtivo."""

    def __init__(self, **kwargs: Any) -> None:
        cliente = kwargs.get("cliente")
        if isinstance(cliente, ClienteStub) and "repositorio_orcamento" not in kwargs:
            workspace = Path(kwargs.get("workspace_base", tempfile.mkdtemp(prefix="kortex-jobs-")))
            kwargs.update(dependencias_stub(cliente, workspace / ".orcamento-teste"))
        super().__init__(**kwargs)
