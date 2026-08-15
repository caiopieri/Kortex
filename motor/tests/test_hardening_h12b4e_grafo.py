import json
import sqlite3
from decimal import Decimal
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.orcamento import CotacaoTentativa, RepositorioOrcamento, ResultadoTentativa, RotaTentativaCusteada
from motor.politica import PoliticaGates
from tests.helpers_grafo import TETO_OPERADOR_TESTE


def test_resume_manual_preserva_veredito_sem_recobrar_evaluator(tmp_path):
    efeitos = []

    class Tentativa:
        def __init__(self, papel, texto):
            self.papel, self.texto = papel, texto

        def cotar_tentativa(self):
            return CotacaoTentativa(Decimal("0.10"), "BRL", "preco-v1")

        def tentar_uma_vez(self):
            efeitos.append(self.papel)
            return ResultadoTentativa(self.texto, Decimal("0.01"), "BRL", self.papel)

    def fabrica(papel, _prompt, _tentativa, _requisitos):
        textos = {
            "verifier": '{"aprovado": true, "motivo": "ok"}',
            "evaluator": '{"aprovado": false, "lacunas": ["persistida"], "nos_a_refazer": []}',
            "synthesizer": "final parcial",
        }
        return [RotaTentativaCusteada(
            f"rota-{papel}", f"provedor-{papel}", Tentativa(papel, textos.get(papel, "saida")),
        )]

    spec = json.loads(
        (Path(__file__).parent.parent / "exemplos" / "missao-pesquisa.json").read_text()
    )
    spec["subagentes"] = spec["subagentes"][:1]
    repo = RepositorioOrcamento(tmp_path / "runs")

    class Legado:
        def chamar(self, papel, _prompt, **_kwargs):
            assert papel == "synthesizer"
            return "final parcial"

    grafo = construir_grafo(
        Legado(),
        LogEventos(tmp_path / "eventos.jsonl"), checkpointer=InMemorySaver(),
        politica=PoliticaGates(overrides={"plano": "prosseguir"}),
        repositorio_orcamento=repo, fabrica_tentativas_orcadas=fabrica,
        teto_bootstrap=TETO_OPERADOR_TESTE,
    )
    config = {"configurable": {"thread_id": "thread-manual"}}
    pausado = grafo.invoke(
        {"spec": spec, "run_id": "run-manual", "thread_id": "thread-manual"}, config,
    )

    assert pausado["__interrupt__"][0].value["lacunas"] == ["persistida"]
    retomado = grafo.invoke(Command(resume="prosseguir"), config)
    assert efeitos.count("evaluator") == 1
    assert retomado["avaliacao"]["lacunas"] == ["persistida"]
    assert retomado["resposta_final"].endswith("final parcial")


def test_duas_reconciliacoes_nao_reusam_identidade_executor_verifier(tmp_path):
    efeitos, avaliacoes = [], 0

    class Tentativa:
        def __init__(self, papel, texto):
            self.papel, self.texto = papel, texto

        def cotar_tentativa(self):
            return CotacaoTentativa(Decimal(".1"), "BRL", "preco-v1")

        def tentar_uma_vez(self):
            efeitos.append(self.papel)
            return ResultadoTentativa(self.texto, Decimal(".01"), "BRL", self.papel)

    def fabrica(papel, _prompt, _tentativa, _requisitos):
        nonlocal avaliacoes
        if papel == "evaluator":
            avaliacoes += 1
            texto = (
                '{"aprovado": false, "lacunas": ["refazer"], "nos_a_refazer": ["pesquisa-alfa"]}'
                if avaliacoes <= 2 else '{"aprovado": true, "lacunas": [], "nos_a_refazer": []}'
            )
        else:
            texto = (
                '{"aprovado": true, "motivo": "ok"}' if papel == "verifier"
                else "final" if papel == "synthesizer" else "saida"
            )
        return [RotaTentativaCusteada(
            f"rota-{papel}", f"provedor-{papel}", Tentativa(papel, texto),
        )]

    spec = json.loads(
        (Path(__file__).parent.parent / "exemplos" / "missao-pesquisa.json").read_text()
    )
    spec["subagentes"] = spec["subagentes"][:1]
    repo = RepositorioOrcamento(tmp_path / "runs-reconciliacao")

    class Legado:
        def chamar(self, papel, _prompt, **_kwargs):
            assert papel == "synthesizer"
            return "final"

    grafo = construir_grafo(
        Legado(), LogEventos(tmp_path / "reconciliacao.jsonl"),
        politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "preencher"}),
        max_rodadas_reconciliacao=2, repositorio_orcamento=repo,
        fabrica_tentativas_orcadas=fabrica,
        teto_bootstrap=TETO_OPERADOR_TESTE,
    )
    resultado = grafo.invoke({"spec": spec, "run_id": "run-r", "thread_id": "thread-r"})

    assert resultado["resposta_final"] == "final"
    with sqlite3.connect(repo.caminho("run-r")) as con:
        calls = [linha[0] for linha in con.execute("SELECT call_id FROM budget_reservation")]
    for papel in ("executor", "verifier"):
        ids = [call for call in calls if call.startswith(f"{papel}-")]
        assert len(ids) == len(set(ids)) == 3
