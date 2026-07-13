from __future__ import annotations

from pathlib import Path

import pytest

from motor.eventos import LogEventos
from tests.audit_corpus import casos, executar_caso, materializar_corpus

CASOS = casos("H06a")
assert len(CASOS) == 7


@pytest.fixture(scope="session")
def corpus_auditoria(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("audit-corpus-h06a"))


@pytest.mark.parametrize("nodeid", CASOS, ids=lambda nodeid: nodeid.split("::", 1)[1])
def test_reprodutor_h06a(corpus_auditoria: Path, nodeid: str) -> None:
    executar_caso(corpus_auditoria, nodeid)


@pytest.mark.parametrize(
    ("reservado", "valor"),
    [("evento", "forjado"), ("t", -1.0), ("seq", 1)],
)
def test_e1_colisao_com_envelope_falha_antes_do_write(
    tmp_path: Path,
    reservado: str,
    valor: object,
) -> None:
    log_path = tmp_path / "log.jsonl"
    log = LogEventos(log_path)
    try:
        with pytest.raises(ValueError, match="reservado"):
            log.evento(
                "spec.recebida",
                **{reservado: valor, "missao": "m1", "subagentes": 1},
            )
    finally:
        log.fechar()

    assert log_path.read_bytes() == b""
