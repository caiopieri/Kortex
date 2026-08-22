"""Guardas de higiene para o workspace usado pelos testes."""

from __future__ import annotations

from pathlib import Path

import pytest


_WORKSPACE = Path("runs")
_IGNORED_PARTS = frozenset({
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__",
})
_IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


def _ignorar(path: Path) -> bool:
    return (
        any(parte in _IGNORED_PARTS for parte in path.parts)
        or path.suffix in _IGNORED_SUFFIXES
    )


def _snapshot_workspace(root: Path) -> dict[str, tuple[str, int]]:
    """Registra apenas artefatos de run; caches de ferramenta não são resíduos."""
    if not root.exists():
        return {}
    snapshot: dict[str, tuple[str, int]] = {}
    for path in root.rglob("*"):
        relativo = path.relative_to(root)
        if _ignorar(relativo):
            continue
        tipo = "dir" if path.is_dir() else "file"
        tamanho = 0 if tipo == "dir" else path.stat().st_size
        snapshot[str(relativo)] = (tipo, tamanho)
    return snapshot


@pytest.fixture(scope="session", autouse=True)
def workspace_de_testes_nao_vaza():
    antes = _snapshot_workspace(_WORKSPACE)
    yield
    depois = _snapshot_workspace(_WORKSPACE)
    adicionados = sorted(set(depois) - set(antes))
    removidos = sorted(set(antes) - set(depois))
    alterados = sorted(
        caminho for caminho in set(antes) & set(depois)
        if antes[caminho] != depois[caminho]
    )
    assert not (adicionados or removidos or alterados), (
        "testes alteraram o workspace de runs; "
        f"caminhos novos: {adicionados}; "
        f"removidos: {removidos}; "
        f"alterados: {alterados}"
    )
