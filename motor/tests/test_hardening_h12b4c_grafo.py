import json
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.modelos import ClienteStub
from motor.orcamento import (
    CotacaoTentativa,
    ErroOrcamento,
    RepositorioOrcamento,
    ResultadoTentativa,
    RotaTentativaCusteada,
)
from motor.politica import PoliticaGates


SPEC = json.loads(
    (Path(__file__).parent.parent / "exemplos" / "missao-pesquisa.json").read_text()
)


class _Tentativa:
    def __init__(self, eventos, texto=None, falhar=False, ao_chamar=None):
        self.eventos, self.texto, self.falhar = eventos, texto, falhar
        self.ao_chamar = ao_chamar

    def cotar_tentativa(self):
        self.eventos.append("cotou")
        return CotacaoTentativa(Decimal("0.10"), "BRL", "preco-v1")

    def tentar_uma_vez(self):
        self.eventos.append("chamou")
        if self.ao_chamar:
            self.ao_chamar()
        if self.falhar:
            raise RuntimeError("custo desconhecido")
        return ResultadoTentativa(self.texto, Decimal("0.01"), "BRL", "usage-1")


def _grafo(tmp_path, repo=None, fabrica=None, legado=None):
    legado = legado or ClienteStub(lambda _papel, _prompt: pytest.fail("cliente.chamar legado"))
    grafo = construir_grafo(
        legado,
        LogEventos(tmp_path / "eventos.jsonl"),
        politica=PoliticaGates(overrides={"plano": "abortar"}),
        repositorio_orcamento=repo,
        fabrica_tentativas_orcadas=fabrica,
    )
    return grafo, legado


def test_planner_reserva_antes_de_cada_retry_e_usa_identidades_distintas(tmp_path):
    repo = RepositorioOrcamento(tmp_path / "runs")
    eventos = []

    def reserva_ja_existe():
        with sqlite3.connect(repo.caminho("run-1")) as con:
            assert con.execute(
                "SELECT status FROM budget_reservation ORDER BY rowid DESC LIMIT 1"
            ).fetchone()[0] == "RESERVED"

    def fabrica(_papel, _prompt, tentativa, _requisitos):
        texto = "sem json" if tentativa == 1 else json.dumps(SPEC)
        return [RotaTentativaCusteada(
            "openai", "openai", _Tentativa(eventos, texto, ao_chamar=reserva_ja_existe),
        )]

    grafo, legado = _grafo(tmp_path, repo, fabrica)
    resultado = grafo.invoke({
        "missao_texto": "pesquise", "run_id": "run-1", "thread_id": "thread-1",
    })

    assert resultado["spec"]["versao"] == "0.1"
    assert legado.chamadas == []
    assert eventos == ["cotou", "chamou", "cotou", "chamou"]
    with sqlite3.connect(repo.caminho("run-1")) as con:
        linhas = con.execute(
            "SELECT reservation_id,call_id,route_id,attempt,status "
            "FROM budget_reservation ORDER BY call_id"
        ).fetchall()
    assert len(linhas) == 2
    assert len({linha[0] for linha in linhas}) == 2
    assert {linha[1] for linha in linhas} == {"planner-spec-1", "planner-spec-2"}
    assert all(linha[2:] == ("openai", 1, "RECONCILED") for linha in linhas)


@pytest.mark.parametrize("ausente", ["repo", "fabrica", "thread"])
def test_planner_falha_fechado_sem_config_ou_identidade(tmp_path, ausente):
    class LegadoReal:
        def __init__(self):
            self.chamadas = []

        def chamar(self, papel, prompt, **_kwargs):
            self.chamadas.append((papel, prompt))
            return "{}"

    legado = LegadoReal()
    repo = None if ausente == "repo" else RepositorioOrcamento(tmp_path / "runs")
    fabrica = (
        None if ausente == "fabrica" else
        lambda *_: [RotaTentativaCusteada("openai", "openai", _Tentativa([], "{}"))]
    )
    entrada = {"missao_texto": "pesquise", "run_id": "run-1", "thread_id": "thread-1"}
    if ausente == "thread":
        entrada.pop("thread_id")
    grafo, legado = _grafo(tmp_path, repo, fabrica, legado)
    with pytest.raises(ErroOrcamento):
        grafo.invoke(entrada)
    assert legado.chamadas == []


def test_custo_desconhecido_invalida_sessao_e_impede_fallback(tmp_path):
    repo = RepositorioOrcamento(tmp_path / "runs")
    primeira, segunda = [], []

    def fabrica(*_):
        return [
            RotaTentativaCusteada("rota-a", "provedor-a", _Tentativa(primeira, falhar=True)),
            RotaTentativaCusteada(
                "rota-b", "provedor-b", _Tentativa(segunda, json.dumps(SPEC)),
            ),
        ]

    grafo, legado = _grafo(tmp_path, repo, fabrica)

    with pytest.raises(RuntimeError, match="planner não produziu"):
        grafo.invoke({
            "missao_texto": "pesquise", "run_id": "run-2", "thread_id": "thread-2",
        })

    assert legado.chamadas == []
    assert primeira.count("chamou") == 1
    assert segunda.count("chamou") == 0
    with sqlite3.connect(repo.caminho("run-2")) as con:
        assert con.execute(
            "SELECT status FROM budget_session"
        ).fetchone()[0] == "INVALIDATED"
