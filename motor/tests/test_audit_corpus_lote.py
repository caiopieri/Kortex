"""O lote de reprodutores ainda REPROVA.

Os 99 reprodutores da auditoria passaram a rodar agrupados por dono, um
subprocesso por dono em vez de um por caso — o que derrubou o gate de 307s para
131s, de volta para dentro do orçamento de 5 minutos da carta.

O risco dessa troca é específico e grave: um lote que sempre devolve "passou"
tem exatamente a mesma aparência de um lote que funciona, porque o estado normal
da suíte é tudo verde. Seria trocar um gate lento por um gate decorativo, e o
corpus inteiro da auditoria viraria enfeite sem ninguém notar.

Daí estes testes: eles provam os DOIS desfechos, que é a única forma de
distinguir contenção que funciona de contenção que aprova tudo.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.audit_corpus import casos, executar_lote, materializar_corpus

CASOS = casos("H08")


@pytest.fixture(scope="module")
def corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("corpus-lote"))


def _sabotar(corpus: Path, nodeid: str) -> None:
    arquivo, _, nome = nodeid.partition("::")
    caminho = corpus / arquivo
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    i = next(n for n, linha in enumerate(linhas) if linha.startswith(f"def {nome}("))
    linhas.insert(i + 1, "    assert False, 'SABOTADO'")
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def test_caso_quebrado_e_atribuido_ao_proprio_nodeid(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Um caso quebrado tem que falhar — e falhar NO LUGAR CERTO.

    Atribuição importa tanto quanto detecção: um lote que acusa falha sem dizer
    qual caso caiu obriga a bissecção manual e, na prática, faz o reprodutor
    deixar de ser usado.
    """
    corpus = materializar_corpus(tmp_path_factory.mktemp("corpus-sabotado"))
    alvo = CASOS[0]
    _sabotar(corpus, alvo)

    resultado = executar_lote(corpus, CASOS)

    assert resultado[alvo] is not None and "SABOTADO" in resultado[alvo]
    # E os vizinhos do mesmo lote continuam limpos: uma falha não contamina o
    # veredito dos outros, senão um caso quebrado esconderia todos os demais.
    assert all(resultado[nodeid] is None for nodeid in CASOS[1:])


def test_lote_intacto_passa_inteiro(corpus: Path) -> None:
    assert all(falha is None for falha in executar_lote(corpus, CASOS).values())


def test_caso_ausente_do_corpus_reprova_em_vez_de_sumir(corpus: Path) -> None:
    """Caso que o manifesto declara e o corpus não tem é regressão do manifesto.

    Se ele apenas não aparecesse no relatório, o lote diria "nenhuma falha" e o
    invariante deixaria de ser provado em silêncio — a pior forma de perder
    cobertura, porque o placar continua verde.
    """
    resultado = executar_lote(corpus, ["tests/inexistente.py::test_fantasma"])
    assert resultado["tests/inexistente.py::test_fantasma"] is not None


def test_lote_sem_relatorio_reprova_todos(tmp_path: Path) -> None:
    """Erro de coleta (corpus vazio) não pode virar gate verde."""
    resultado = executar_lote(tmp_path, CASOS)
    assert all(falha is not None for falha in resultado.values())


def test_todos_os_reprodutores_do_manifesto_continuam_individualizados() -> None:
    """O agrupamento é de EXECUÇÃO, não de contagem.

    A carta exige que todo invariante tenha um teste que o prove; se o lote
    tivesse colapsado 99 casos em 13 testes, a contagem cairia e a evidência
    junto.
    """
    donos = ["H01", "H02", "H03", "H04", "H05a", "H06a", "H06b", "H07",
             "H08", "H09a", "H09b", "H10a", "H11"]
    assert sum(len(casos(dono)) for dono in donos) == 99
