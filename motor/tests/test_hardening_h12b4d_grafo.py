import json
import sqlite3
from decimal import Decimal

import pytest

from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.orcamento import (
    CotacaoTentativa, ErroOrcamento,
    RequisitosTentativaCusteada,
    RepositorioOrcamento,
    ResultadoTentativa,
    RotaTentativaCusteada,
)
from motor.politica import PoliticaGates
from tests.specs import spec_pesquisa, spec_pesquisa_um


BASE_SPEC = spec_pesquisa_um()


class _Tentativa:
    def __init__(self, eventos, texto, maximo=Decimal("0.10"), falhar=False):
        self.eventos, self.texto, self.maximo, self.falhar = eventos, texto, maximo, falhar

    def cotar_tentativa(self):
        return CotacaoTentativa(self.maximo, "BRL", "preco-v1")

    def tentar_uma_vez(self):
        self.eventos.append("efeito")
        if self.falhar:
            raise RuntimeError("resultado ambiguo")
        return ResultadoTentativa(self.texto, Decimal("0.01"), "BRL", "usage-1")


def _spec(*, quantidade=1, teto=2.0, tentativas=1):
    spec = json.loads(json.dumps(BASE_SPEC))
    if quantidade != 1:
        spec["subagentes"] = spec_pesquisa()["subagentes"][:quantidade]
    spec["restricoes"]["teto_custo"] = teto
    spec["restricoes"]["max_tentativas"] = tentativas
    return spec


def _invocar(tmp_path, spec, fabrica):
    repo = RepositorioOrcamento(tmp_path / "runs")

    class Legado:
        def chamar(self, papel, _prompt, **_kwargs):
            if papel == "evaluator":
                return '{"aprovado": true, "lacunas": [], "nos_a_refazer": []}'
            if papel == "synthesizer":
                return "final"
            raise AssertionError(f"chamada legada proibida: {papel}")

    grafo = construir_grafo(
        Legado(),
        LogEventos(tmp_path / "eventos.jsonl"),
        politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "prosseguir"}),
        repositorio_orcamento=repo,
        fabrica_tentativas_orcadas=fabrica,
    )
    resultado = grafo.invoke({
        "spec": spec, "run_id": "run-1", "thread_id": "thread-1",
    })
    return repo, resultado


def test_orcamento_insuficiente_impede_efeito_do_executor(tmp_path):
    efeitos = []

    def fabrica(_papel, _prompt, _tentativa, _requisitos):
        return [RotaTentativaCusteada(
            "executor-a", "provedor-a", _Tentativa(efeitos, "saida", Decimal("0.11")),
        )]

    _, resultado = _invocar(tmp_path, _spec(teto=0.10), fabrica)

    assert efeitos == []
    assert resultado["resultados"][0]["aprovado"] is False


def test_teto_bootstrap_governa_reserva_e_spec_gerada(tmp_path):
    efeitos = []
    repo = RepositorioOrcamento(tmp_path / "runs-bootstrap")
    spec_acima = json.dumps(_spec(teto=3))

    def fabrica(_papel, _prompt, _tentativa, _requisitos):
        return [RotaTentativaCusteada(
            "planner-a", "provedor-a", _Tentativa(efeitos, spec_acima, Decimal("0.1")),
        )]

    grafo = construir_grafo(
        object(), LogEventos(tmp_path / "eventos-bootstrap.jsonl"),
        repositorio_orcamento=repo, fabrica_tentativas_orcadas=fabrica,
        teto_bootstrap=Decimal("0.5"),
    )

    with pytest.raises(RuntimeError, match="planner não produziu"):
        grafo.invoke({"missao_texto": "missao", "run_id": "run-b", "thread_id": "thread-b"})

    assert efeitos == ["efeito", "efeito", "efeito"]
    assert repo.sessao("run-b", "thread-b", Decimal("0.5")).teto == Decimal("0.5")


@pytest.mark.parametrize("teto", [Decimal("0"), Decimal("NaN"), "2"])
def test_teto_bootstrap_injetado_invalido_falha_fechado(tmp_path, teto):
    with pytest.raises(ErroOrcamento, match="teto bootstrap invalido"):
        construir_grafo(object(), LogEventos(tmp_path / "eventos-invalido.jsonl"),
                        teto_bootstrap=teto)


@pytest.mark.parametrize(
    ("papel_alvo", "modo", "efeitos_esperados"),
    [("evaluator", "teto", 2), ("evaluator", "ambiguo", 3),
     ("synthesizer", "teto", 3), ("synthesizer", "ambiguo", 4)],
)
def test_fase_final_falha_fechado_sem_sintese(tmp_path, papel_alvo, modo, efeitos_esperados):
    efeitos = []

    def fabrica(papel, _prompt, _tentativa, _requisitos):
        textos = {
            "verifier": '{"aprovado": true, "motivo": "ok"}',
            "evaluator": '{"aprovado": true, "lacunas": [], "nos_a_refazer": []}',
            "synthesizer": "final",
        }
        return [RotaTentativaCusteada(
            f"rota-{papel}", f"provedor-{papel}", _Tentativa(
                efeitos, textos.get(papel, "saida"),
                maximo=Decimal("3") if modo == "teto" and papel == papel_alvo else Decimal(".1"),
                falhar=modo == "ambiguo" and papel == papel_alvo,
            ),
        )]

    _repo, resultado = _invocar(tmp_path, _spec(), fabrica)
    assert len(efeitos) == efeitos_esperados
    assert resultado["avaliacao"]["abortada"] is True
    assert "resposta_final" not in resultado


def test_fan_out_usa_identidades_unicas_por_no(tmp_path):
    efeitos = []

    def fabrica(papel, _prompt, _tentativa, _requisitos):
        textos = {
            "verifier": '{"aprovado": true, "motivo": "ok"}',
            "evaluator": '{"aprovado": true, "lacunas": [], "nos_a_refazer": []}',
            "synthesizer": "final",
        }
        texto = textos.get(papel, "saida")
        return [RotaTentativaCusteada(
            f"rota-{papel}", f"provedor-{papel}", _Tentativa(efeitos, texto),
        )]

    repo, _ = _invocar(tmp_path, _spec(quantidade=2), fabrica)
    with sqlite3.connect(repo.caminho("run-1")) as con:
        linhas = con.execute(
            "SELECT reservation_id,call_id FROM budget_reservation"
        ).fetchall()

    assert len(linhas) == 6
    assert len({linha[0] for linha in linhas}) == 6
    assert len({linha[1] for linha in linhas}) == 6


def test_verifier_faz_reserva_separada_do_executor(tmp_path):
    efeitos = []

    def fabrica(papel, _prompt, _tentativa, _requisitos):
        textos = {
            "verifier": '{"aprovado": true, "motivo": "ok"}',
            "evaluator": '{"aprovado": true, "lacunas": [], "nos_a_refazer": []}',
            "synthesizer": "final",
        }
        texto = textos.get(papel, "saida")
        return [RotaTentativaCusteada(
            f"rota-{papel}", f"provedor-{papel}", _Tentativa(efeitos, texto),
        )]

    repo, resultado = _invocar(tmp_path, _spec(), fabrica)
    with sqlite3.connect(repo.caminho("run-1")) as con:
        fases = [linha[0].split("-", 1)[0] for linha in con.execute(
            "SELECT call_id FROM budget_reservation WHERE call_id LIKE 'executor-%' "
            "OR call_id LIKE 'verifier-%' ORDER BY rowid"
        )]

    assert fases == ["executor", "verifier"]
    assert resultado["resultados"][0]["aprovado"] is True


def test_erro_ambiguo_invalida_sessao_e_nao_chega_ao_verifier_ou_retry(tmp_path):
    efeitos, papeis = [], []

    def fabrica(papel, _prompt, _tentativa, _requisitos):
        papeis.append(papel)
        return [RotaTentativaCusteada(
            f"rota-{papel}", f"provedor-{papel}",
            _Tentativa(efeitos, "saida", falhar=papel != "verifier"),
        )]

    repo, resultado = _invocar(tmp_path, _spec(tentativas=2), fabrica)
    with sqlite3.connect(repo.caminho("run-1")) as con:
        status = con.execute("SELECT status FROM budget_session").fetchone()[0]

    assert efeitos == ["efeito"]
    assert "verifier" not in papeis
    assert resultado["avaliacao"]["abortada"] is True
    assert "resposta_final" not in resultado
    assert status == "INVALIDATED"


def test_fallback_informa_rota_efetiva_e_verifier_nao_autoavalia(tmp_path):
    efeitos = []
    spec = _spec()
    spec["subagentes"][0].update({
        "tier": "media",
        "ferramentas": "web",
        "capacidades_requeridas": ["pesquisa", "redacao"],
    })

    class Legado:
        roteamento_capacidades_runtime = True

        def chamar(self, papel, _prompt, **_kwargs):
            if papel == "evaluator":
                return '{"aprovado": true, "lacunas": [], "nos_a_refazer": []}'
            if papel == "synthesizer":
                return "final"
            raise AssertionError(f"chamada legada proibida: {papel}")

    class Tentativa:
        def __init__(self, marcador, texto):
            self.marcador, self.texto = marcador, texto

        def cotar_tentativa(self):
            return CotacaoTentativa(Decimal("0.10"), "BRL", "preco-v1")

        def tentar_uma_vez(self):
            efeitos.append(self.marcador)
            return ResultadoTentativa(self.texto, Decimal("0.01"), "BRL", self.marcador)

    def fabrica(papel, _prompt, _tentativa, recebidos):
        assert isinstance(recebidos, RequisitosTentativaCusteada)
        if papel == "pesquisador":
            assert recebidos == RequisitosTentativaCusteada(
                tier="media", ferramentas="web", capacidades=("pesquisa", "redacao"),
            )
            return [
                RotaTentativaCusteada(
                    "alias-a", "provedor-a", Tentativa("executor-a", None),
                ),
                RotaTentativaCusteada(
                    "alias-b-executor", "provedor-b", Tentativa("executor-b", "saida"),
                ),
            ]
        if papel == "verifier":
            assert recebidos.evitar_provedor == "provedor-b"
            return [
                RotaTentativaCusteada(
                    "alias-b-verifier", "provedor-b",
                    Tentativa("verifier-b-proibido", '{"aprovado": true}'),
                ),
                RotaTentativaCusteada(
                    "alias-c", "provedor-c",
                    Tentativa("verifier-c", '{"aprovado": true, "motivo": "ok"}'),
                ),
            ]
        texto = (
            '{"aprovado": true, "lacunas": [], "nos_a_refazer": []}'
            if papel == "evaluator" else "final"
        )
        return [RotaTentativaCusteada(
            f"alias-{papel}", f"provedor-{papel}", Tentativa(papel, texto),
        )]

    grafo = construir_grafo(
        Legado(), LogEventos(tmp_path / "eventos-requisitos.jsonl"),
        politica=PoliticaGates(overrides={"plano": "prosseguir", "cobertura": "prosseguir"}),
        repositorio_orcamento=RepositorioOrcamento(tmp_path / "runs-requisitos"),
        fabrica_tentativas_orcadas=fabrica,
    )
    resultado = grafo.invoke({
        "spec": spec, "run_id": "run-requisitos", "thread_id": "thread-requisitos",
    })

    assert efeitos == ["executor-a", "executor-b", "verifier-c", "evaluator", "synthesizer"]
    assert resultado["resultados"][0]["aprovado"] is True
