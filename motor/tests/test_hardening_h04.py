from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from motor.grafo import construir_grafo
from tests.audit_corpus import casos, executar_caso, materializar_corpus
from tests.runner_fake import RunnerFake


@pytest.fixture(scope="module")
def corpus_h04(tmp_path_factory: pytest.TempPathFactory):
    return materializar_corpus(tmp_path_factory.mktemp("audit-corpus-h04"))


@pytest.mark.parametrize("nodeid", casos("H04"))
def test_reprodutor_h04(corpus_h04, nodeid: str) -> None:
    executar_caso(corpus_h04, nodeid, plugins=("tests.runner_fake",))


class _Nulo:
    def chamar(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    evento = chamar


def _executar(
    tmp_path: Path,
    comando: str,
    entradas: dict[str, Any],
    allowlist: list[str],
) -> dict[str, Any]:
    grafo = construir_grafo(
        cast(Any, _Nulo()),
        cast(Any, _Nulo()),
        ferramentas_permitidas=allowlist,
        command_runner=RunnerFake(),
    )
    sub = {
        "id": "validador",
        "tipo": "validador",
        "valida": "alvo",
        "validador": {"kind": "comando", "config": {"comando": comando}},
        "entradas": entradas,
    }
    retorno = grafo.nodes["subagente"].invoke(
        {
            "sub": sub,
            "spec": {"missao": {}, "restricoes": {"max_tentativas": 1}},
            "deps": {"alvo": "resultado"},
            "workspace": tmp_path,
        }
    )
    return cast(dict[str, Any], retorno["resultados"][0])


def test_placeholder_nao_pode_selecionar_executavel(tmp_path: Path) -> None:
    resultado = _executar(
        tmp_path,
        "{python} -c pass",
        {"python": sys.executable},
        [sys.executable],
    )
    assert resultado["aprovado"] is False
    assert "selecionar executável" in resultado["motivo"]


def test_placeholder_parcial_nao_pode_fabricar_opcao(tmp_path: Path) -> None:
    marcador = tmp_path / "executado"
    codigo = "from pathlib import Path;import sys;Path(sys.argv[1]).write_text('x')"
    resultado = _executar(
        tmp_path,
        f"{sys.executable} {{prefixo}}c {shlex.quote(codigo)} {{marcador}}",
        {"prefixo": "-", "marcador": marcador},
        [sys.executable],
    )
    assert resultado["aprovado"] is False
    assert not marcador.exists()


def test_fim_de_opcoes_preserva_posicional_iniciado_por_hifen(tmp_path: Path) -> None:
    script = tmp_path / "eco.py"
    script.write_text("import sys;print(sys.argv[-1])\n", encoding="utf-8")
    resultado = _executar(
        tmp_path,
        f"{sys.executable} {script} -- {{valor}}",
        {"valor": "-arquivo"},
        [sys.executable],
    )
    evidencia = json.loads(resultado["saida"])["evidencia"]
    assert resultado["aprovado"] is True
    assert evidencia["saida"] == "-arquivo"


@pytest.mark.parametrize("alvo", ["diretorio", "arquivo"])
def test_allowlist_rejeita_alvo_nao_executavel(tmp_path: Path, alvo: str) -> None:
    caminho = tmp_path / alvo
    if alvo == "diretorio":
        caminho.mkdir()
    else:
        caminho.write_text("sem permissao de execucao", encoding="utf-8")

    resultado = _executar(tmp_path, str(caminho), {}, [str(caminho)])
    assert resultado["aprovado"] is False
