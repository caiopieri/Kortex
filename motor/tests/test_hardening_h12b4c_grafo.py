import json
import sqlite3
from decimal import Decimal

import pytest

import motor.grafo as modulo_grafo
from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.modelos import ClienteStub
from motor.orcamento import (
    CotacaoTentativa,
    ErroOrcamento,
    RepositorioOrcamento,
    ResultadoTentativa,
    RotaTentativaCusteada,
    TentativaBloqueadaPreEfeito,
    TentativaReconciliada,
    TentativaTerminal,
)
from motor.politica import PoliticaGates
from tests.helpers_grafo import TETO_OPERADOR_TESTE
from tests.specs import spec_pesquisa_um


SPEC = spec_pesquisa_um()


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
        teto_bootstrap=TETO_OPERADOR_TESTE,
    )
    return grafo, legado


def _invocar_executor_com_resultado(
    tmp_path, monkeypatch, resultado_executor,
):
    repo = RepositorioOrcamento(tmp_path / "runs-executor")
    log = LogEventos(tmp_path / "eventos-executor.jsonl")
    chamadas = []

    def executar(_repo, _sessao, identidade, _adaptador):
        chamadas.append(identidade.route_id)
        if identidade.route_id.startswith("executor-"):
            return resultado_executor(identidade.route_id)
        respostas = {
            "apoio-verifier": json.dumps({"aprovado": True, "motivo": "ok"}),
            "apoio-evaluator": json.dumps({"aprovado": True, "lacunas": []}),
            "apoio-synthesizer": "síntese",
        }
        return TentativaReconciliada(ResultadoTentativa(
            respostas[identidade.route_id], Decimal("0"), "BRL", "usage-apoio",
        ))

    def fabrica(papel, *_):
        if papel == "pesquisador":
            return [
                RotaTentativaCusteada("executor-a", "provedor-a", object()),
                RotaTentativaCusteada("executor-b", "provedor-b", object()),
            ]
        return [RotaTentativaCusteada(
            f"apoio-{papel}", f"provedor-{papel}", object(),
        )]

    spec = json.loads(json.dumps(SPEC))
    spec["subagentes"] = [spec["subagentes"][0]]
    spec["restricoes"]["max_tentativas"] = 1
    spec["restricoes"]["teto_custo"] = 2
    monkeypatch.setattr(modulo_grafo, "executar_tentativa_custeada", executar)
    grafo = construir_grafo(
        ClienteStub(lambda *_: pytest.fail("cliente legado não deve ser chamado")),
        log,
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        repositorio_orcamento=repo,
        fabrica_tentativas_orcadas=fabrica,
        teto_bootstrap=TETO_OPERADOR_TESTE,
    )
    try:
        grafo.invoke({"spec": spec, "run_id": "run-executor", "thread_id": "thread"})
    finally:
        log.fechar()
    eventos = [
        json.loads(linha)
        for linha in (tmp_path / "eventos-executor.jsonl").read_text().splitlines()
    ]
    chamadas_executor = [rota for rota in chamadas if rota.startswith("executor-")]
    motivos_executor = [
        evento["motivo"] for evento in eventos
        if evento["evento"] == "executor.erro"
        and evento["executor"] == SPEC["subagentes"][0]["id"]
    ]
    return chamadas_executor, motivos_executor


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


def test_grafo_tenta_rota_b_depois_de_bloqueio_pre_efeito(
    tmp_path, monkeypatch,
):
    repo = RepositorioOrcamento(tmp_path / "runs-seguro")
    chamadas = []

    def executar(_repo, _sessao, identidade, _adaptador):
        chamadas.append(identidade.route_id)
        if identidade.route_id == "rota-a":
            return TentativaBloqueadaPreEfeito("sem_cotacao")
        return TentativaReconciliada(
            ResultadoTentativa(json.dumps(SPEC), Decimal("0"), "BRL", "usage-b"),
        )

    def fabrica(*_):
        return [
            RotaTentativaCusteada("rota-a", "provedor-a", object()),
            RotaTentativaCusteada("rota-b", "provedor-b", object()),
        ]

    monkeypatch.setattr(modulo_grafo, "executar_tentativa_custeada", executar)
    grafo, _legado = _grafo(tmp_path, repo, fabrica)

    resultado = grafo.invoke({
        "missao_texto": "pesquise", "run_id": "run-seguro", "thread_id": "thread-seguro",
    })

    assert resultado["spec"]["versao"] == "0.1"
    assert chamadas == ["rota-a", "rota-b"]


def test_grafo_nao_tenta_rota_b_depois_de_terminal(tmp_path, monkeypatch):
    repo = RepositorioOrcamento(tmp_path / "runs-terminal")
    chamadas = []

    def executar(_repo, _sessao, identidade, _adaptador):
        chamadas.append(identidade.route_id)
        if identidade.route_id == "rota-a":
            return TentativaTerminal(
                "reserva anterior pode ter produzido efeito", "REPLAY_AMBIGUO",
            )
        return TentativaReconciliada(
            ResultadoTentativa(json.dumps(SPEC), Decimal("0"), "BRL", "usage-b"),
        )

    def fabrica(*_):
        return [
            RotaTentativaCusteada("rota-a", "provedor-a", object()),
            RotaTentativaCusteada("rota-b", "provedor-b", object()),
        ]

    monkeypatch.setattr(modulo_grafo, "executar_tentativa_custeada", executar)
    grafo, _legado = _grafo(tmp_path, repo, fabrica)

    with pytest.raises(RuntimeError, match="planner não produziu"):
        grafo.invoke({
            "missao_texto": "pesquise", "run_id": "run-terminal",
            "thread_id": "thread-terminal",
        })

    assert chamadas == ["rota-a", "rota-a", "rota-a"]


def test_executor_loga_teto_quando_toda_cadeia_e_bloqueada_antes_do_efeito(
    tmp_path, monkeypatch,
):
    chamadas, motivos = _invocar_executor_com_resultado(
        tmp_path, monkeypatch, lambda _rota: TentativaBloqueadaPreEfeito("teto"),
    )

    assert chamadas == ["executor-a", "executor-b"]
    assert motivos == [
        "bloqueio pré-efeito: executor-a=teto; executor-b=teto",
    ]
    assert "modelo não respondeu" not in motivos


def test_executor_loga_terminal_e_nao_tenta_fallback(tmp_path, monkeypatch):
    chamadas, motivos = _invocar_executor_com_resultado(
        tmp_path,
        monkeypatch,
        lambda _rota: TentativaTerminal(
            "reserva anterior pode ter produzido efeito", "REPLAY_AMBIGUO",
        ),
    )

    assert chamadas == ["executor-a"]
    assert motivos == [
        "reserva anterior pode ter produzido efeito (REPLAY_AMBIGUO)",
    ]


def test_executor_preserva_status_terminal_ao_truncar_motivo(tmp_path, monkeypatch):
    _chamadas, motivos = _invocar_executor_com_resultado(
        tmp_path,
        monkeypatch,
        lambda _rota: TentativaTerminal("x" * 500, "REPLAY_AMBIGUO"),
    )

    assert motivos == [f"{'x' * 360} (REPLAY_AMBIGUO)"]


def test_executor_so_diz_modelo_nao_respondeu_apos_chamada_reconciliada_sem_texto(
    tmp_path, monkeypatch,
):
    chamadas, motivos = _invocar_executor_com_resultado(
        tmp_path,
        monkeypatch,
        lambda _rota: TentativaReconciliada(
            ResultadoTentativa(None, Decimal("0"), "BRL", "usage-sem-texto"),
        ),
    )

    assert chamadas == ["executor-a", "executor-b"]
    assert motivos == ["modelo não respondeu"]


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
