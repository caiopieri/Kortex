from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

import motor.grafo as grafo


def _spec_grafo_dependencias() -> dict[str, Any]:
    sub = {
        "id": "a",
        "papel": "a",
        "objetivo": "produzir a",
        "entradas": {},
        "resultado_esperado": "a",
        "rubrica": ["entrega a"],
        "depende_de": [],
        "tier": "simples",
        "capacidades_requeridas": ["redacao"],
    }
    return {
        "versao": "0.1",
        "missao": {
            "id": "auditoria-c",
            "objetivo": "exercitar o grafo",
            "contexto": "teste deterministico",
            "criterios_cobertura": ["todos os nos foram avaliados"],
        },
        "padrao": "grafo_dependencias",
        "subagentes": [sub, {**sub, "id": "b", "papel": "b", "depende_de": ["a"]}],
        "sintese": {"instrucao": "sintetize", "formato": "markdown"},
        "restricoes": {"max_tentativas": 1},
    }


class LogMemoria:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, dict[str, Any]]] = []

    def evento(self, tipo: str, **dados: Any) -> None:
        self.eventos.append((tipo, dados))


class Politica:
    def __init__(self, cobertura_manual: bool = False) -> None:
        self.cobertura_manual = cobertura_manual

    def decisao_auto(self, portao: str, default: str | None = None) -> str | None:
        if portao == "cobertura" and self.cobertura_manual:
            return None
        return "prosseguir"


class FalhaModelo(RuntimeError):
    pass


class Cliente:
    def __init__(self, falha_em: str | None = None, cobertura_reprovada: bool = False) -> None:
        self.falha_em = falha_em
        self.cobertura_reprovada = cobertura_reprovada
        self.chamadas_sintese = 0

    def chamar(self, papel: str, prompt: str, **kwargs: Any) -> str:
        if (self.falha_em == "executor" and papel == "a") or papel == self.falha_em:
            raise FalhaModelo(f"falha em {papel}")
        if papel == "verifier":
            return '{"aprovado": true, "motivo": ""}'
        if papel == "evaluator":
            if self.cobertura_reprovada:
                return '{"aprovado": false, "lacunas": ["a incompleto"], "nos_a_refazer": ["a"]}'
            return '{"aprovado": true, "lacunas": [], "nos_a_refazer": []}'
        if papel == "synthesizer":
            self.chamadas_sintese += 1
            return "sintese parcial"
        return f"saida-{papel}"


def test_g3_decisao_de_cobertura_desconhecida_nao_autoriza_parcial(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    decisoes = iter(["decisao-desconhecida", "abortar"])
    monkeypatch.setattr(grafo, "interrupt", lambda payload: next(decisoes))
    cliente = Cliente(cobertura_reprovada=True)

    estado = grafo.construir_grafo(
        cast(Any, cliente),
        cast(Any, LogMemoria()),
        politica=cast(Any, Politica(cobertura_manual=True)),
        workspace_base=tmp_path,
        max_rodadas_reconciliacao=0,
    ).invoke({"spec": _spec_grafo_dependencias()})

    assert cliente.chamadas_sintese == 0
    assert estado["avaliacao"].get("abortada") is True


@pytest.mark.parametrize("falha_em", ["executor", "verifier"])
def test_g4_excecao_de_modelo_vira_evento_e_resultado_reprovado(
    falha_em: str,
    tmp_path: Path,
) -> None:
    log = LogMemoria()
    try:
        estado = grafo.construir_grafo(
            cast(Any, Cliente(falha_em=falha_em)),
            cast(Any, log),
            politica=cast(Any, Politica()),
            workspace_base=tmp_path,
        ).invoke({"spec": _spec_grafo_dependencias()})
    except FalhaModelo as exc:
        pytest.fail(f"a excecao do modelo escapou do grafo: {exc}")

    resultado_a = next(r for r in estado["resultados"] if r["id"] == "a")
    assert resultado_a["aprovado"] is False
    assert any(tipo == "executor.erro" for tipo, _ in log.eventos)
