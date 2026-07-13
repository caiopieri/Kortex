import pytest

from motor.runner import CommandResult
from tests.audit_corpus import casos, executar_caso, materializar_corpus


@pytest.fixture(scope="module")
def corpus_h05a(tmp_path_factory: pytest.TempPathFactory):
    return materializar_corpus(tmp_path_factory.mktemp("audit-corpus-h05a"))


@pytest.mark.parametrize("nodeid", casos("H05a"))
def test_reprodutor_h05a(corpus_h05a, nodeid: str) -> None:
    executar_caso(corpus_h05a, nodeid)


def test_resultado_do_runner_expoe_timeout_e_truncamento_tipados() -> None:
    resultado = CommandResult(timed_out=True, truncated=True)
    assert resultado.timed_out is True
    assert resultado.truncated is True
