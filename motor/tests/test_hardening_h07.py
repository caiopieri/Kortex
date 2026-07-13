from __future__ import annotations

from pathlib import Path

import pytest

from tests.audit_corpus import casos, executar_caso, materializar_corpus


CASOS_H07 = casos("H07")


@pytest.fixture(scope="module")
def corpus_h07(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("corpus-h07"))


def test_manifest_h07_tem_quatro_casos_autoritativos() -> None:
    assert len(CASOS_H07) == 4


@pytest.mark.parametrize("nodeid", CASOS_H07)
def test_reprodutor_h07(corpus_h07: Path, nodeid: str) -> None:
    executar_caso(corpus_h07, nodeid)
