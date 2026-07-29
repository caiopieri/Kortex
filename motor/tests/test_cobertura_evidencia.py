"""A razão processo/opinião é a métrica do produto — então ela é medida e dita.

O buraco que isto fecha: até 2026-07-29, uma missão com ZERO portão de processo
terminava com uma resposta tão confiante quanto uma cujos testes passaram.
Ausência de prova era indistinguível de prova — o pior modo de falha possível
para um produto cuja tese inteira é a prova.

A landing promete "nada vira 'pronto' sem prova que atravesse um portão". Quem
lê a resposta precisa conseguir dizer QUE portão foi esse.
"""
from __future__ import annotations

from typing import Any

import pytest

from motor.grafo import carimbar_evidencia, cobertura_de_evidencia


def _spec(*subagentes: dict[str, Any]) -> dict[str, Any]:
    return {"missao": {"id": "m"}, "subagentes": list(subagentes)}


def _produtor(node_id: str, *nomes: str) -> dict[str, Any]:
    return {
        "id": node_id, "papel": "executor",
        "produz_artefatos": [{"nome": nome, "tipo": "python"} for nome in nomes],
    }


def _validador(node_id: str, alvo: str, kind: str) -> dict[str, Any]:
    return {
        "id": node_id, "tipo": "validador", "valida": alvo,
        "validador": {"kind": kind, "config": {}},
    }


# ------------------------------------------------------- classificação
@pytest.mark.parametrize(
    ("kind", "prova"),
    [("comando", "execucao"), ("schema_json", "estrutural"),
     ("contem", "estrutural")],
)
def test_kind_do_validador_define_a_forca_da_prova(kind: str, prova: str) -> None:
    spec = _spec(_produtor("cod", "a.py"), _validador("v", "cod", kind))
    assert cobertura_de_evidencia(spec)["artefatos"][0]["prova"] == prova


def test_artefato_sem_validador_conta_como_opiniao() -> None:
    """Sem validador, quem julgou foi o verifier — um modelo lendo o texto.

    É o default, e é exatamente o que qualquer um consegue encadeando LLMs.
    """
    cobertura = cobertura_de_evidencia(_spec(_produtor("cod", "a.py")))
    assert cobertura["artefatos"][0]["prova"] == "opiniao"
    assert (cobertura["execucao"], cobertura["total"]) == (0, 1)


def test_prova_mais_forte_vence_quando_ha_varios_validadores() -> None:
    """Quem roda a suíte E confere o schema está coberto por execução."""
    spec = _spec(
        _produtor("cod", "a.py"),
        _validador("v1", "cod", "schema_json"),
        _validador("v2", "cod", "comando"),
    )
    assert cobertura_de_evidencia(spec)["artefatos"][0]["prova"] == "execucao"


def test_no_que_nao_produz_artefato_fica_fora_da_conta() -> None:
    """A métrica é sobre entregáveis, não sobre nós.

    Contar um pesquisador que só produz texto como "artefato não coberto"
    encheria o carimbo de ruído e ensinaria a ignorá-lo.
    """
    spec = _spec({"id": "pesquisa", "papel": "executor"}, _produtor("cod", "a.py"))
    assert [a["id"] for a in cobertura_de_evidencia(spec)["artefatos"]] == ["cod"]


def test_validador_de_kind_desconhecido_nao_conta_como_prova() -> None:
    """Falha fechada: kind inválido reprova no motor, então não pode contar aqui.

    O risco específico é uma spec com typo em `kind` parecer coberta na métrica
    e reprovar na execução — métrica mentindo para melhor.
    """
    spec = _spec(_produtor("cod", "a.py"), _validador("v", "cod", "comand"))
    assert cobertura_de_evidencia(spec)["artefatos"][0]["prova"] == "opiniao"


@pytest.mark.parametrize("spec", [{}, {"subagentes": None}, {"subagentes": "x"}])
def test_spec_degenerada_nao_estoura(spec: dict[str, Any]) -> None:
    assert cobertura_de_evidencia(spec) == {"artefatos": [], "execucao": 0, "total": 0}


# ------------------------------------------------------- carimbo
def test_carimbo_declara_a_razao_e_nomeia_o_que_ficou_descoberto() -> None:
    spec = _spec(
        _produtor("cod", "ebay.py"),
        _produtor("testador", "testes.py"),
        _validador("prova", "testador", "comando"),
    )
    texto = carimbar_evidencia("RESPOSTA", {"spec": spec})

    assert texto.startswith("RESPOSTA")
    assert "1 de 2 artefatos passaram por portão de execução" in texto
    assert "cod (ebay.py): verificado só por opinião de modelo" in texto
    # O que passou não vira linha: o rodapé lista o que falta provar.
    assert "testador (testes.py)" not in texto


def test_carimbo_distingue_forma_de_comportamento() -> None:
    """`schema_json` prova que o JSON tem o formato certo, não que está certo."""
    spec = _spec(_produtor("cod", "saida.json"), _validador("v", "cod", "schema_json"))
    texto = carimbar_evidencia("R", {"spec": spec})

    assert "0 de 1" in texto
    assert "checado só na forma, não no comportamento" in texto


def test_cobertura_total_nao_lista_ninguem() -> None:
    spec = _spec(_produtor("cod", "a.py"), _validador("v", "cod", "comando"))
    texto = carimbar_evidencia("R", {"spec": spec})

    assert "1 de 1 artefatos passaram por portão de execução" in texto
    assert "- cod" not in texto


def test_missao_sem_artefato_nao_recebe_carimbo() -> None:
    """Missão de texto não tem o que executar.

    Carimbar aviso nela treinaria a ignorar o carimbo — e o de reprovação vai
    junto quando isso acontece.
    """
    spec = _spec({"id": "pesquisa", "papel": "executor"})
    assert carimbar_evidencia("R", {"spec": spec}) == "R"


def test_carimbo_nao_depende_do_que_o_modelo_escreveu() -> None:
    """Fato montado do estado, não narrativa: o sintetizador não pode negá-lo.

    Um sintetizador que afirma "todos os testes passaram" num run sem nenhum
    portão de execução continua sendo desmentido no rodapé.
    """
    spec = _spec(_produtor("cod", "a.py"))
    texto = carimbar_evidencia(
        "Todos os testes passaram e o código está pronto para produção.",
        {"spec": spec},
    )
    assert "0 de 1 artefatos passaram por portão de execução" in texto
