"""Compatibilidade para executar o Curador a partir da raiz do repositorio.

O pacote distribuido continua sendo ``motor/motor``. Este adaptador existe apenas
no checkout, onde o diretorio externo ``motor`` e descoberto como namespace.
"""

from .motor.curador import (  # type: ignore[import-not-found]
    analisar,
    carregar_runs,
    certificar_sombra,
    formatar_certificacao_markdown,
    formatar_custo_markdown,
    formatar_markdown,
    formatar_promocao_markdown,
    formatar_proposta_markdown,
    formatar_sombra_markdown,
    main,
    preparar_promocao_gated,
    propor,
    rodar_sombra,
)

__all__ = [
    "analisar",
    "carregar_runs",
    "certificar_sombra",
    "formatar_certificacao_markdown",
    "formatar_custo_markdown",
    "formatar_markdown",
    "formatar_promocao_markdown",
    "formatar_proposta_markdown",
    "formatar_sombra_markdown",
    "main",
    "preparar_promocao_gated",
    "propor",
    "rodar_sombra",
]


if __name__ == "__main__":
    raise SystemExit(main())
