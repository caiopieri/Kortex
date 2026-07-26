"""Reprodutores da auditoria independente (grupo G/grafo-reconciliacao e C/comando).

Cada teste aqui DEMONSTRA uma falha de invariante; nenhum deles conserta codigo.
"""
from __future__ import annotations

import json
import sys
from typing import Any, cast


try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # pragma: no cover
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from motor.eventos import LogEventos
from motor.modelos import ClienteStub
from motor.politica import PoliticaGates
from motor.runner import CommandRequest, CommandResult
from tests.helpers_grafo import construir_grafo_teste as construir_grafo


def _sub(sid: str, depende_de: list[str] | None = None, **extra: Any) -> dict:
    return {
        "id": sid,
        "papel": "executor",
        "objetivo": f"Executar etapa {sid}",
        "entradas": {},
        "resultado_esperado": f"Saida da etapa {sid}",
        "rubrica": ["entrega saida textual"],
        "depende_de": depende_de or [],
        **extra,
    }


def _spec(subagentes: list[dict], padrao: str = "grafo_dependencias") -> dict:
    return {
        "versao": "0.1",
        "padrao": padrao,
        "missao": {
            "id": "auditoria-gc",
            "objetivo": "Auditar reconciliacao e comando",
            "contexto": "",
            "criterios_cobertura": ["todos os subagentes aprovados"],
        },
        "restricoes": {"teto_custo": 2.0, "max_subagentes": 10, "max_tentativas": 1},
        "subagentes": subagentes,
        "gates": [],
        "sintese": {"instrucao": "Sintetize", "formato": "markdown"},
    }


# ---------------------------------------------------------------- G2 ---------


def test_g2_atribuicao_a_montante_do_evaluator_e_descartada_quando_ha_reprovado(tmp_path):
    """G2: o no culpado a MONTANTE some do veredito se algum no ficou reprovado.

    Cadeia A -> B. B reprova no verifier. O evaluator (seguindo PROMPT_EVALUATOR)
    aponta 'A' como origem da lacuna. `avaliar_cobertura` reconstroi o veredito no
    ramo `if reprovados:` SEM a chave `nos_a_refazer` (grafo.py:1147-1149) e, na
    linha seguinte, le `veredito.get("nos_a_refazer", [])` do dict ja reconstruido
    (grafo.py:1150-1153). Resultado: a atribuicao do evaluator e perdida e a
    reconciliacao refaz apenas o sintoma (B), nunca a causa (A).
    """

    def roteador(papel: str, prompt: str):
        if papel == "executor":
            return "SAIDA"
        if papel == "verifier":
            aprovado = "subagente 'B'" not in prompt
            return json.dumps({"aprovado": aprovado, "motivo": "B incoerente com A"})
        if papel == "evaluator":
            return json.dumps({
                "aprovado": False,
                "lacunas": ["a especificacao A contradiz o resultado"],
                "nos_a_refazer": ["A"],
            })
        return "FINAL"

    log = LogEventos(tmp_path / "log.jsonl")
    grafo = construir_grafo(
        ClienteStub(roteador), log, checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "prosseguir"}),
    )
    resultado = grafo.invoke(
        {"spec": _spec([_sub("A"), _sub("B", ["A"])])},
        {"configurable": {"thread_id": "g2-montante"}},
    )
    nos = resultado["avaliacao"]["nos_a_refazer"]
    assert "A" in nos, (
        "G2 violado: o no a montante apontado pelo evaluator foi descartado; "
        f"nos_a_refazer={nos}"
    )


# ---------------------------------------------------------------- G4 ---------


def test_g4_nome_de_artefato_com_separador_derruba_o_motor(tmp_path):
    """G4: `produz_artefatos[*].nome` vem da spec (gerada pelo planner LLM) e nunca
    e validado — `Subagente.produz_artefatos` e `list[dict[str, Any]]` (spec.py:110).
    `registrar_artefato` (grafo.py:342-349) concatena o nome direto no path e so faz
    `mkdir` da raiz; qualquer nome com separador levanta OSError fora de try
    (grafo.py:773) e derruba o run inteiro, sem evento e sem resultado reprovado.
    A travessia so nao vaza porque o prefixo `{id}__` cola em `..` — acidente de
    formatacao, nao validacao.
    """
    workspace = tmp_path / "runs" / "r1" / "artefatos"

    grafo = construir_grafo(
        ClienteStub(lambda papel, prompt: (
            "CONTEUDO VAZADO" if papel == "executor"
            else json.dumps({"aprovado": True, "motivo": "ok"})
        )),
        LogEventos(tmp_path / "log.jsonl"),
    )
    sub = _sub("no", produz_artefatos=[{"nome": "sub/dir/saida.md", "tipo": "texto"}])
    retorno = grafo.nodes["subagente"].invoke({
        "sub": sub,
        "spec": _spec([sub]),
        "workspace": workspace,
        "run_id": "r1",
        "thread_id": "r1",
    })
    assert retorno["resultados"][0]["aprovado"] is False


def test_g4_artefato_sem_campo_nome_derruba_o_motor(tmp_path):
    """G4: spec com `produz_artefatos: [{}]` levanta KeyError em grafo.py:772,
    fora de qualquer try — crash do run, sem evento e sem resultado reprovado.
    """
    grafo = construir_grafo(
        ClienteStub(lambda papel, prompt: (
            "SAIDA" if papel == "executor"
            else json.dumps({"aprovado": True, "motivo": "ok"})
        )),
        LogEventos(tmp_path / "log.jsonl"),
    )
    sub = _sub("no", produz_artefatos=[{"tipo": "texto"}])
    retorno = grafo.nodes["subagente"].invoke({
        "sub": sub, "spec": _spec([sub]), "workspace": tmp_path / "ws",
        "run_id": "r1", "thread_id": "r1",
    })
    assert retorno["resultados"][0]["aprovado"] is False


# ---------------------------------------------------------------- C1/C4 -----


class _RunnerExplode:
    """Adapter externo mal-comportado: a fronteira deve conte-lo, nao propagar."""

    def run(self, request: CommandRequest) -> CommandResult:
        raise RuntimeError("backend de sandbox pifou")


def _validador_comando(tmp_path, comando: str, entradas: dict, allowlist: list[str],
                       runner: Any) -> dict:
    grafo = construir_grafo(
        ClienteStub(lambda papel, prompt: None),
        LogEventos(tmp_path / "log.jsonl"),
        ferramentas_permitidas=allowlist,
        command_runner=cast(Any, runner),
    )
    sub = {
        "id": "validador", "tipo": "validador", "valida": "alvo",
        "validador": {"kind": "comando", "config": {"comando": comando}},
        "entradas": entradas,
    }
    retorno = grafo.nodes["subagente"].invoke({
        "sub": sub,
        "spec": {"missao": {}, "restricoes": {"max_tentativas": 1}},
        "deps": {"alvo": "resultado"},
        "workspace": tmp_path / "ws",
    })
    return cast(dict, retorno["resultados"][0])


def test_c1_excecao_do_runner_nao_e_contida_pela_fronteira(tmp_path):
    """C1/G4: `executar_comando_seguro` chama `command_runner.run` sem try
    (grafo.py:875-879). Qualquer adapter que levante (contrato `CommandRunner` nao
    e validado — runner.py:57-60) derruba o run inteiro em vez de virar reprovacao.
    """
    resultado = _validador_comando(
        tmp_path, f"{sys.executable} -c pass", {}, [sys.executable], _RunnerExplode(),
    )
    assert resultado["aprovado"] is False
    assert resultado["motivo"]


def test_c4_byte_nulo_em_entrada_derruba_o_motor(tmp_path):
    """C4: `executar_comando_seguro` valida shell/opcao/identidade mas nao valida o
    CONTEUDO dos argumentos. Um `\\x00` numa entrada da spec chega ao backend e faz
    `subprocess` levantar `ValueError: embedded null byte` — que nem o
    `DockerSandboxRunner` (runner.py:252 so captura `OSError`) nem
    `executar_comando_seguro` (grafo.py:875) contem. Crash do run, nao reprovacao.
    """
    from tests.runner_fake import RunnerFake

    resultado = _validador_comando(
        tmp_path, f"{sys.executable} -c pass {{v}}", {"v": "a\x00b"},
        [sys.executable], RunnerFake(),
    )
    assert resultado["aprovado"] is False
