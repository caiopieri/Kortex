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

from motor.grafo import AVISO_IMITACAO, carimbar_evidencia, cobertura_de_evidencia


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
    assert cobertura_de_evidencia(spec) == {
        "artefatos": [], "execucao": 0, "total": 0, "medido": False,
    }


# ------------------------------------------------------- carimbo
def test_carimbo_declara_a_razao_e_nomeia_o_que_ficou_descoberto() -> None:
    spec = _spec(
        _produtor("cod", "ebay.py"),
        _produtor("testador", "testes.py"),
        _validador("prova", "testador", "comando"),
    )
    # `resultados` presente porque o carimbo mede o que ACONTECEU: sem o veredito
    # do validador, o portão conta como não-provado (falha fechada).
    texto = carimbar_evidencia("RESPOSTA", {
        "spec": spec, "resultados": [{"id": "prova", "aprovado": True}],
    })

    assert texto.startswith("RESPOSTA")
    assert "1 de 2 artefatos passaram por portão de execução" in texto
    assert "cod (ebay.py): verificado só por opinião de modelo" in texto
    # O que passou não vira linha: o rodapé lista o que falta provar.
    assert "testador (testes.py)" not in texto


def test_carimbo_distingue_forma_de_comportamento() -> None:
    """`schema_json` prova que o JSON tem o formato certo, não que está certo."""
    spec = _spec(_produtor("cod", "saida.json"), _validador("v", "cod", "schema_json"))
    texto = carimbar_evidencia("R", {
        "spec": spec, "resultados": [{"id": "v", "aprovado": True}],
    })

    assert "0 de 1" in texto
    assert "checado só na forma, não no comportamento" in texto


def test_cobertura_total_nao_lista_ninguem() -> None:
    spec = _spec(_produtor("cod", "a.py"), _validador("v", "cod", "comando"))
    texto = carimbar_evidencia("R", {
        "spec": spec, "resultados": [{"id": "v", "aprovado": True}],
    })

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


# ------------------------------------------------------- achados da trava GPT-5
# Auditoria de fronteira dupla, 2026-07-29. Os dois achados abaixo eram do mesmo
# tipo — a métrica reportando MAIS cobertura do que existia — que é exatamente o
# que ela nunca pode fazer, já que a resposta inteira se apoia nela.
def test_C01_denominador_conta_artefatos_e_nao_nos() -> None:
    """Um nó com 100 artefatos descobertos pesava igual a um nó com 1 coberto.

    Reportava "1 de 2 = 50%" onde a cobertura real era 1 de 101 (~1%).
    """
    spec = _spec(
        _produtor("a", "um.py"),
        _produtor("b", *[f"x{i}.py" for i in range(100)]),
        _validador("v", "a", "comando"),
    )
    cobertura = cobertura_de_evidencia(spec)

    assert (cobertura["execucao"], cobertura["total"]) == (1, 101)


def test_C02_portao_que_reprovou_nao_conta_como_prova() -> None:
    """"passaram por portão de execução" é afirmação sobre RESULTADO.

    A versão anterior lia só a configuração da spec e escrevia que o artefato
    passou mesmo com o validador tendo saído com exit code 1.
    """
    spec = _spec(_produtor("a", "um.py"), _validador("v", "a", "comando"))
    state = {"spec": spec, "resultados": [
        {"id": "a", "aprovado": True},
        {"id": "v", "aprovado": False, "motivo": "exit_code=1"},
    ]}
    texto = carimbar_evidencia("R", state)

    assert "0 de 1 artefatos passaram por portão de execução" in texto
    assert "portão de execução NÃO aprovou este artefato" in texto


def test_C02_portao_que_nem_rodou_tambem_nao_conta() -> None:
    """Ausente do log é não-prova pelo mesmo motivo que reprovado: ninguém viu.

    É o caso mais traiçoeiro — dependência falhou, o validador nunca executou, e
    o rodapé afirmaria cobertura que jamais foi medida.
    """
    spec = _spec(_produtor("a", "um.py"), _validador("v", "a", "comando"))
    state = {"spec": spec, "resultados": [{"id": "a", "aprovado": True}]}

    assert "0 de 1" in carimbar_evidencia("R", state)


def test_C02_portao_aprovado_continua_contando() -> None:
    """O outro desfecho: sem isto, "nunca conta" seria indistinguível de correto."""
    spec = _spec(_produtor("a", "um.py"), _validador("v", "a", "comando"))
    state = {"spec": spec, "resultados": [
        {"id": "a", "aprovado": True}, {"id": "v", "aprovado": True},
    ]}

    assert "1 de 1 artefatos passaram por portão de execução" in carimbar_evidencia("R", state)


def test_sem_resultados_mede_o_que_a_spec_promete() -> None:
    """A leitura spec-only continua existindo: é o que o corpus de exemplos checa.

    Ela mede promessa, não resultado — e por isso não é a que vai para a resposta.
    """
    spec = _spec(_produtor("a", "um.py"), _validador("v", "a", "comando"))
    assert cobertura_de_evidencia(spec)["execucao"] == 1
    assert cobertura_de_evidencia(spec, [])["execucao"] == 0


def test_C04_aprovado_precisa_ser_bool_de_verdade() -> None:
    """`bool("false")` é True — e a métrica de cobertura é o último lugar onde
    coerção generosa pode entrar, porque a resposta inteira se apoia nela.

    Achado da 2ª rodada da trava GPT-5. O motor só emite bool aqui hoje; o teste
    existe para que continuar assim não dependa de sorte.
    """
    spec = _spec(_produtor("a", "um.py"), _validador("v", "a", "comando"))
    for falso in ["false", "não", 1, [1], {"x": 1}]:
        state = {"spec": spec, "resultados": [{"id": "v", "aprovado": falso}]}
        assert "0 de 1" in carimbar_evidencia("R", state), falso

    state = {"spec": spec, "resultados": [{"id": "v", "aprovado": True}]}
    assert "1 de 1" in carimbar_evidencia("R", state)


def test_R3_carimbo_imitado_pelo_sintetizador_e_desautorizado() -> None:
    """O sintetizador não pode escrever o carimbo — só imitá-lo, e visivelmente.

    Achado da 3ª rodada da trava GPT-5: o carimbo era concatenado, então bastava
    o modelo escrever a mesma frase com números melhores para a resposta ter duas
    coberturas em conflito. Quem lesse a primeira levava a forjada.
    """
    spec = _spec(_produtor("a", "um.py"))
    forjado = "Cobertura de evidência: 100 de 100 artefatos passaram por portão de execução."
    texto = carimbar_evidencia(forjado, {"spec": spec, "resultados": []})

    assert AVISO_IMITACAO + forjado in texto
    # E o carimbo real, no fim, continua dizendo a verdade.
    assert texto.rstrip().endswith("verificado só por opinião de modelo")
    assert "0 de 1 artefatos passaram por portão de execução" in texto


def test_R3_imitacao_do_banner_de_reprovacao_tambem_e_desautorizada() -> None:
    spec = _spec(_produtor("a", "um.py"))
    texto = carimbar_evidencia("⚠️ RUN REPROVADO — mentira", {"spec": spec, "resultados": []})

    assert texto.startswith(AVISO_IMITACAO + "⚠️ RUN REPROVADO")


def test_R3_retentativa_conta_pelo_veredito_final() -> None:
    """Id repetido em `resultados` é retentativa, e o último veredito é o que vale.

    A trava leu last-wins como defeito. Só seria se a ordem viesse de fora; ela
    vem do append cronológico do motor. Este teste fixa a semântica nos dois
    sentidos para que a decisão não vire acidente.
    """
    spec = _spec(_produtor("a", "um.py"), _validador("v", "a", "comando"))

    reprovou_depois_passou = {"spec": spec, "resultados": [
        {"id": "v", "aprovado": False}, {"id": "v", "aprovado": True}]}
    assert "1 de 1" in carimbar_evidencia("R", reprovou_depois_passou)

    passou_depois_reprovou = {"spec": spec, "resultados": [
        {"id": "v", "aprovado": True}, {"id": "v", "aprovado": False}]}
    assert "0 de 1" in carimbar_evidencia("R", passou_depois_reprovou)


def test_C08_saida_distingue_promessa_de_medicao() -> None:
    """Os dois modos não podem ter a mesma cara na saída.

    Sem `medido`, um consumidor futuro publicaria "cobertura da spec" como se
    fosse cobertura observada, e o número pareceria idêntico. Achado da 4ª
    rodada da trava GPT-5.
    """
    spec = _spec(_produtor("a", "um.py"), _validador("v", "a", "comando"))

    assert cobertura_de_evidencia(spec)["medido"] is False
    assert cobertura_de_evidencia(spec, [])["medido"] is True


def test_C09_id_vazio_nao_vira_chave_curinga() -> None:
    """Validador sem id e resultado sem id viravam ambos "" e casavam.

    A spec exige id não vazio, então isto é cinto e suspensório — mas string
    vazia como chave é o tipo de acidente que só aparece depois de virar buraco.
    """
    spec = _spec(
        _produtor("p", "um.py"),
        {"tipo": "validador", "valida": "p", "validador": {"kind": "comando", "config": {}}},
    )
    cobertura = cobertura_de_evidencia(spec, [{"aprovado": True}])

    assert cobertura["execucao"] == 0
