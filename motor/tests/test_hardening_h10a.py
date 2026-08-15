from pathlib import Path
from typing import Any, cast

import pytest

from motor.caixa import CaixaFundador
from motor.servico import _validar_job_id
from tests.audit_corpus import casos, executar_lote, materializar_corpus


CASOS_H10A = casos("H10a")


@pytest.fixture(scope="module")
def corpus_h10a(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("corpus-h10a"))


def test_manifest_h10a_tem_sete_casos() -> None:
    assert len(CASOS_H10A) == 7


@pytest.fixture(scope="module")
def _lote_h10a(corpus_h10a) -> dict[str, str | None]:
    """Roda os casos deste dono num subprocesso só.

    Um subprocesso por caso pagava ~4,7s de arranque de interpretador para
    milissegundos de trabalho útil. A atribuição por caso continua: cada
    reprodutor abaixo lê o próprio veredito.
    """
    return executar_lote(corpus_h10a, CASOS_H10A)


@pytest.mark.parametrize("nodeid", CASOS_H10A)
def test_reprodutor_h10a(_lote_h10a: dict[str, str | None], nodeid: str) -> None:
    assert _lote_h10a[nodeid] is None, _lote_h10a[nodeid]


class _Log:
    def evento(self, _tipo: str, **_dados: Any) -> None:
        pass


@pytest.mark.parametrize(
    "portao",
    ["", " gate", "gate ", ".", "..", "a/b", "a\\b", "gate\nforjado", "gate\tforjado"],
)
def test_portao_fora_do_dominio_falha_antes_de_criar_nota(
    tmp_path: Path,
    portao: str,
) -> None:
    caixa = CaixaFundador(tmp_path, _Log())
    with pytest.raises(ValueError, match="portao"):
        caixa.escrever_nota(portao, "?", "contexto", "sim | nao")
    assert list(tmp_path.iterdir()) == []


def test_symlink_quebrado_nao_equivale_a_nota_ausente(tmp_path: Path) -> None:
    nota = tmp_path / "PENDENTE — gate.md"
    nota.symlink_to(tmp_path / "fora-da-caixa.md")

    with pytest.raises(ValueError, match="nota"):
        CaixaFundador(tmp_path, _Log()).ler_decisao("gate")


@pytest.mark.parametrize(
    "job_id",
    [None, 1, "", ".", "..", ".oculto", "../x", "x/y", "x\\y", "x\nforjado"],
)
def test_job_id_fora_do_dominio_canonico_eh_rejeitado(job_id: object) -> None:
    with pytest.raises(ValueError, match="job_id"):
        _validar_job_id(cast(str, job_id))


def test_job_id_canonico_permanece_valido() -> None:
    _validar_job_id("job-01_execucao.v2")
