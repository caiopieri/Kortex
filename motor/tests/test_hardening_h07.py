from __future__ import annotations

from pathlib import Path

import pytest

from tests.audit_corpus import casos, executar_lote, materializar_corpus


CASOS_H07 = casos("H07")


@pytest.fixture(scope="module")
def corpus_h07(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("corpus-h07"))


def test_manifest_h07_tem_quatro_casos_autoritativos() -> None:
    assert len(CASOS_H07) == 4


@pytest.fixture(scope="module")
def _lote_h07(corpus_h07) -> dict[str, str | None]:
    """Roda os casos deste dono num subprocesso só.

    Um subprocesso por caso pagava ~4,7s de arranque de interpretador para
    milissegundos de trabalho útil. A atribuição por caso continua: cada
    reprodutor abaixo lê o próprio veredito.
    """
    return executar_lote(corpus_h07, CASOS_H07)


@pytest.mark.parametrize("nodeid", CASOS_H07)
def test_reprodutor_h07(_lote_h07: dict[str, str | None], nodeid: str) -> None:
    assert _lote_h07[nodeid] is None, _lote_h07[nodeid]
