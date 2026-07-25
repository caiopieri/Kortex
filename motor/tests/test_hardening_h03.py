from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from motor.grafo import construir_grafo
from motor.orcamento import (
    CotacaoTentativa,
    RepositorioOrcamento,
    ResultadoTentativa,
    RotaTentativaCusteada,
)
from tests.audit_corpus import casos, executar_caso, materializar_corpus

CASOS = casos("H03")
assert len(CASOS) == 4


@pytest.fixture(scope="session")
def corpus_auditoria(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return materializar_corpus(tmp_path_factory.mktemp("audit-corpus-h03"))


@pytest.mark.parametrize("nodeid", CASOS, ids=lambda nodeid: nodeid.split("::", 1)[1])
def test_reprodutor_h03(corpus_auditoria: Path, nodeid: str) -> None:
    executar_caso(corpus_auditoria, nodeid)


def _sub(sid: str, depende_de: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": sid,
        "papel": sid,
        "objetivo": f"produzir {sid}",
        "entradas": {},
        "resultado_esperado": sid,
        "rubrica": [f"entrega {sid}"],
        "depende_de": depende_de or [],
    }


def _spec(subagentes: list[dict[str, Any]], max_tentativas: int = 1) -> dict[str, Any]:
    return {
        "padrao": "grafo_dependencias",
        "missao": {
            "id": "hardening-h03",
            "objetivo": "validar falhas parciais",
            "contexto": "teste deterministico",
            "criterios_cobertura": ["todos os nos aprovados"],
        },
        "restricoes": {"max_tentativas": max_tentativas},
        "subagentes": subagentes,
        "sintese": {"instrucao": "sintetize", "formato": "markdown"},
    }


class _LogMemoria:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, Any]]] = []

    def evento(self, tipo: str, **dados: Any) -> None:
        self.eventos.append((tipo, dados))


class _Politica:
    def __init__(self, reconciliar: bool = False) -> None:
        self.reconciliar = reconciliar
        self.cobertura = 0

    def decisao_auto(self, portao: str, default: str | None = None) -> str:
        if portao != "cobertura" or not self.reconciliar:
            return "prosseguir"
        self.cobertura += 1
        return "preencher" if self.cobertura == 1 else "prosseguir"


def _invocar(
    tmp_path: Path,
    spec: dict[str, Any],
    cliente: object,
    log: _LogMemoria,
    politica: _Politica | None = None,
) -> dict[str, Any]:
    class Tentativa:
        def __init__(self, papel: str, prompt: str) -> None:
            self.papel, self.prompt = papel, prompt

        def cotar_tentativa(self) -> CotacaoTentativa:
            return CotacaoTentativa(Decimal("0.10"), "BRL", "teste-v1")

        def tentar_uma_vez(self) -> ResultadoTentativa:
            texto = cast(Any, cliente).chamar(self.papel, self.prompt)
            return ResultadoTentativa(texto, Decimal("0.01"), "BRL", "teste-uso")

    grafo = construir_grafo(
        cast(Any, cliente),
        cast(Any, log),
        politica=cast(Any, politica or _Politica()),
        workspace_base=tmp_path,
        max_rodadas_reconciliacao=1,
        repositorio_orcamento=RepositorioOrcamento(tmp_path / "orcamento"),
        fabrica_tentativas_orcadas=lambda papel, prompt, _tentativa, _requisitos: [
            RotaTentativaCusteada(
                f"teste:{papel}", f"teste-provider:{papel}", Tentativa(papel, prompt),
            )
        ],
    )
    return cast(dict[str, Any], grafo.invoke({
        "spec": spec, "run_id": "h03", "thread_id": "h03",
    }))


@pytest.mark.parametrize(
    ("fronteira", "motivo"),
    [
        ("executor", "falha externa do executor"),
        ("verifier", "falha externa do verifier"),
    ],
)
def test_excecao_externa_preserva_retry_sem_vazar_detalhe(
    tmp_path: Path,
    fronteira: str,
    motivo: str,
) -> None:
    class Cliente:
        def __init__(self) -> None:
            self.chamadas: Counter[str] = Counter()

        def chamar(self, papel: str, _prompt: str, **_kwargs: Any) -> str:
            self.chamadas[papel] += 1
            if papel == ("A" if fronteira == "executor" else "verifier"):
                if self.chamadas[papel] == 1:
                    raise RuntimeError("detalhe confidencial do provedor")
            if papel in {"verifier", "evaluator"}:
                return json.dumps({"aprovado": True})
            return f"saida-{papel}"

    cliente = Cliente()
    log = _LogMemoria()
    estado = _invocar(tmp_path, _spec([_sub("A")], max_tentativas=2), cliente, log)

    assert estado["resultados"][0]["aprovado"] is False
    assert cliente.chamadas["A"] == 1
    assert cliente.chamadas["verifier"] == (1 if fronteira == "verifier" else 0)
    erros = [dados for tipo, dados in log.eventos if tipo == "executor.erro"]
    assert any(dados["motivo"] == "modelo não respondeu" for dados in erros)
    assert "detalhe confidencial" not in json.dumps(log.eventos, ensure_ascii=False)


def test_excecao_do_executor_vira_reprovacao_e_evento(tmp_path: Path) -> None:
    class Cliente:
        def chamar(self, papel: str, _prompt: str, **_kwargs: Any) -> str:
            if papel == "A":
                raise RuntimeError("falha injetada")
            return json.dumps({"aprovado": True})

    log = _LogMemoria()
    estado = _invocar(tmp_path, _spec([_sub("A")]), Cliente(), log)

    assert estado["resultados"][0]["aprovado"] is False
    assert any(tipo == "executor.erro" for tipo, _dados in log.eventos)


def test_reconciliacao_bloqueia_dependente_se_fonte_reprovar(tmp_path: Path) -> None:
    class Cliente:
        def __init__(self) -> None:
            self.chamadas: Counter[str] = Counter()

        def chamar(self, papel: str, _prompt: str, **_kwargs: Any) -> str:
            self.chamadas[papel] += 1
            if papel == "verifier":
                aprovado = self.chamadas[papel] < 3
                return json.dumps({"aprovado": aprovado, "motivo": "fonte reprovada"})
            if papel == "evaluator":
                if self.chamadas[papel] == 1:
                    return json.dumps(
                        {
                            "aprovado": False,
                            "lacunas": ["A incompleto"],
                            "nos_a_refazer": ["A"],
                        }
                    )
                return json.dumps({"aprovado": True})
            return f"saida-{papel}-{self.chamadas[papel]}"

    cliente = Cliente()
    log = _LogMemoria()
    estado = _invocar(
        tmp_path,
        _spec([_sub("A"), _sub("B", ["A"])]),
        cliente,
        log,
        _Politica(reconciliar=True),
    )

    por_id = {resultado["id"]: resultado for resultado in estado["resultados"]}
    assert cliente.chamadas["B"] == 1
    assert por_id["A"]["aprovado"] is False
    assert por_id["B"] == {
        "id": "B",
        "saida": "",
        "tentativas": 0,
        "aprovado": False,
        "motivo": "dependencias reprovadas: A",
    }
    assert any(
        tipo == "portao.reprovado" and dados.get("portao") == "dependencias:B"
        for tipo, dados in log.eventos
    )
