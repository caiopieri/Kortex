"""O corpus de exemplos não pode regredir em cobertura de evidência.

"Portão de evidência" é o diferencial declarado do produto. Um corpus de
exemplos onde tudo é julgado por modelo demonstra o contrário do que a landing
promete — e é o estado natural para onde as coisas escorregam, porque escrever
`comando` dá mais trabalho que escrever uma rubrica.

Estes testes existem para que essa erosão fique vermelha em vez de silenciosa.
"""
from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

import pytest

from motor.grafo import cobertura_de_evidencia
from motor.spec import WorkflowSpec

EXEMPLOS = Path(__file__).parents[1] / "exemplos"

# Missões cujo entregável é código executável. São as que TÊM que ter portão de
# processo; missão de texto (pesquisa, RAG, redação) não tem o que executar, e
# exigir `comando` dela seria teatro — exatamente o que o Kortex diz combater.
SPECS_DE_CODIGO = ["sandbox-prova-de-vida", "ebay-com-portao-de-processo"]


def _specs() -> list[tuple[str, dict[str, Any]]]:
    encontradas = []
    for arquivo in sorted(EXEMPLOS.glob("*.json")):
        try:
            dados = json.loads(arquivo.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(dados, dict) and isinstance(dados.get("subagentes"), list):
            encontradas.append((arquivo.stem, dados))
    return encontradas


@pytest.mark.parametrize("nome", SPECS_DE_CODIGO)
def test_spec_de_codigo_tem_todo_artefato_coberto_por_execucao(nome: str) -> None:
    """Nestas, opinião de modelo não basta para nenhum entregável."""
    dados = json.loads((EXEMPLOS / f"{nome}.json").read_text(encoding="utf-8"))
    cobertura = cobertura_de_evidencia(dados)

    descobertos = [a["id"] for a in cobertura["artefatos"] if a["prova"] != "execucao"]
    assert cobertura["total"] > 0, "spec de código sem artefato declarado"
    assert not descobertos, f"artefatos sem portão de execução: {descobertos}"


@pytest.mark.parametrize("nome", SPECS_DE_CODIGO)
def test_spec_de_codigo_e_valida_de_verdade(nome: str) -> None:
    """A cobertura é lida da spec, então a spec precisa ser aceita pelo motor.

    Sem isto, dava para inflar a métrica com um validador que o motor rejeitaria
    na hora de rodar.
    """
    dados = json.loads((EXEMPLOS / f"{nome}.json").read_text(encoding="utf-8"))
    WorkflowSpec.model_validate(dados)


def test_ebay_distingue_segredo_operacional_de_fixture_de_teste() -> None:
    dados = json.loads((EXEMPLOS / "ebay-com-portao-de-processo.json").read_text(encoding="utf-8"))
    criterio = dados["missao"]["criterios_cobertura"][2].lower()

    assert "segredo operacional real" in criterio
    assert "aparece hardcoded no código, em log ou em mensagem de erro" in criterio
    assert "fixtures ou mocks de teste são permitidos" in criterio


def test_ebay_contrato_exercita_chamadas_canonicas_da_api_publica() -> None:
    dados = json.loads((EXEMPLOS / "ebay-com-portao-de-processo.json").read_text(encoding="utf-8"))
    contrato = dados["subagentes"][2]["validador"]["config"]["comando"]

    assert "callable(m.obter_token)" in contrato
    assert "min_price=10, max_price=50" in contrato
    assert "token='fixture-token'" in contrato
    assert "patch.object(m.requests, 'post'" in contrato
    assert "patch.object(m.requests, 'get'" in contrato
    assert "token_mock.assert_called_once()" in contrato
    assert "search_mock.assert_called_once()" in contrato
    assert "caso.assertRaises(Exception, m.buscar)" in contrato
    assert "caso.assertRaises(Exception, m.buscar, '')" in contrato
    assert "conditions:{{NEW}},buyingOptions:{{FIXED_PRICE}}" in contrato
    argumento_python = shlex.split(contrato)[2].format_map({})
    compile(argumento_python, "<contrato-do-modulo>", "exec")
    assert "price:[10..50],conditions:{NEW},buyingOptions:{FIXED_PRICE}" in argumento_python


def test_corpus_nao_regride_a_razao_processo_opiniao() -> None:
    """Piso da razão no corpus inteiro, artefato a artefato.

    O número é baixo de propósito: a maioria dos exemplos é de texto e nunca vai
    ter portão de execução. O que este piso impede é o caso perigoso — alguém
    remover um `comando` existente, ou acrescentar missão de código sem portão, e
    ninguém perceber.
    """
    total = execucao = 0
    for _nome, dados in _specs():
        cobertura = cobertura_de_evidencia(dados)
        total += cobertura["total"]
        execucao += cobertura["execucao"]

    assert total >= 6, "corpus perdeu artefatos declarados"
    assert execucao / total >= 0.6, f"razão caiu para {execucao}/{total}"


def test_todo_artefato_declarado_pertence_a_uma_spec_valida() -> None:
    """Impede o truque inverso: declarar artefato sem produzir spec executável."""
    for nome, dados in _specs():
        if cobertura_de_evidencia(dados)["total"]:
            WorkflowSpec.model_validate(dados), nome
