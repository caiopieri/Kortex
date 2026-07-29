import pytest

from motor.runner import CommandResult
from tests.audit_corpus import casos, executar_lote, materializar_corpus


@pytest.fixture(scope="module")
def corpus_h05a(tmp_path_factory: pytest.TempPathFactory):
    return materializar_corpus(tmp_path_factory.mktemp("audit-corpus-h05a"))


@pytest.fixture(scope="module")
def _lote_h05a(corpus_h05a) -> dict[str, str | None]:
    """Roda os casos deste dono num subprocesso só.

    Um subprocesso por caso pagava ~4,7s de arranque de interpretador para
    milissegundos de trabalho útil. A atribuição por caso continua: cada
    reprodutor abaixo lê o próprio veredito.
    """
    return executar_lote(corpus_h05a, casos("H05a"))


@pytest.mark.parametrize("nodeid", casos("H05a"))
def test_reprodutor_h05a(_lote_h05a: dict[str, str | None], nodeid: str) -> None:
    assert _lote_h05a[nodeid] is None, _lote_h05a[nodeid]


def test_resultado_do_runner_expoe_timeout_e_truncamento_tipados() -> None:
    resultado = CommandResult(timed_out=True, truncated=True)
    assert resultado.timed_out is True
    assert resultado.truncated is True
