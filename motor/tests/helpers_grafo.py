"""Infraestrutura offline de testes; nunca importar em código de produção."""
from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from motor.composicao_orcamento import DependenciasOrcamento, RotaOrcadaCertificada
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


def topologia_stub() -> tuple[RotaOrcadaCertificada, ...]:
    """Topologia offline explícita; não é evidência de providers reais."""
    return (
        RotaOrcadaCertificada(
            "stub:executor", "stub-provider-executor", frozenset({"executor"}),
        ),
        RotaOrcadaCertificada(
            "stub:verifier", "stub-provider-verifier", frozenset({"verifier"}),
        ),
    )


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
        papel: str, prompt: str, _tentativa: int, requisitos: RequisitosTentativaCusteada,
    ) -> list[RotaTentativaCusteada]:
        papel_topologia = "verifier" if papel == "verifier" else "executor"
        provider_id = f"stub-provider-{papel_topologia}"
        if requisitos.evitar_provedor == provider_id:
            return []
        return [RotaTentativaCusteada(
            f"stub:{papel_topologia}", provider_id, TentativaStub(papel, prompt),
        )]

    return {"repositorio_orcamento": repo, "fabrica_tentativas_orcadas": fabricar}


def composicao_stub(cliente: ClienteStub, raiz: Path | None = None) -> DependenciasOrcamento:
    deps = dependencias_stub(cliente, raiz)
    return DependenciasOrcamento(
        cliente, deps["repositorio_orcamento"],
        deps["fabrica_tentativas_orcadas"], topologia_stub(), Decimal("2"),
    )


def dependencias_servico_stub(
    cliente: ClienteStub, raiz: Path | None = None,
) -> dict[str, Any]:
    return {
        **dependencias_stub(cliente, raiz),
        "rotas_certificadas": topologia_stub(),
        "teto_bootstrap": Decimal("2"),
    }


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
        if isinstance(cliente, ClienteStub):
            if "repositorio_orcamento" not in kwargs:
                workspace = Path(
                    kwargs.get("workspace_base", tempfile.mkdtemp(prefix="kortex-jobs-"))
                )
                kwargs.update(dependencias_servico_stub(
                    cliente, workspace / ".orcamento-teste",
                ))
            elif "rotas_certificadas" not in kwargs:
                raise ValueError("deps explicitas de teste exigem topologia")
        super().__init__(**kwargs)
