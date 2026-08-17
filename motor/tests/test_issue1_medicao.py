from __future__ import annotations

import json
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from motor import __main__ as cli
from motor.composicao_orcamento import (
    PRICING_CAPTURADO_EM,
    PRICING_MAX_AGE_S,
    compor_orcamento_omniroute,
)
from motor.eventos import LogEventos
from motor.grafo import construir_grafo
from motor.modelos import ClienteStub
from motor.orcamento import ErroOrcamento, RequisitosTentativaCusteada, RotaTentativaCusteada
from motor.politica import PoliticaGates
from tests.helpers_grafo import TETO_OPERADOR_TESTE


def _cfg() -> dict:
    """Fixture mínima, independente do scratchpad, para a composição OmniRoute."""
    return {
        "omniroute": {
            "base_url": "http://localhost:20128/v1",
            "api_key_env": "KORTEX_ISSUE1_API_KEY",
            "papeis": {
                "executor": {
                    "modelo": "codex/gpt-5.6-luna",
                    "provider_id": "openai",
                    "max_input_tokens": 1000,
                    "max_completion_tokens": 100,
                },
                "verifier": {
                    "modelo": "claude/claude-opus-4-8",
                    "provider_id": "anthropic",
                    "max_input_tokens": 1000,
                    "max_completion_tokens": 100,
                },
            },
        },
        "fx": {
            "versao": "fx-issue1",
            "capturado_em": 1,
            "cotacao_venda": "5.20",
        },
        "fx_max_age_s": 86400,
        "margem": "1.20",
        "teto_bootstrap_brl": "150",
        "timeout": 30,
    }


def _resposta() -> tuple[int, dict[str, str], bytes]:
    return 200, {"X-Request-ID": "issue1-request"}, json.dumps({
        "model": "gpt-5.6-luna",
        "choices": [{"message": {"content": "resposta sem medicao"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
    }).encode()


def test_N1_sem_declaracao_preserva_credencial_e_frescor(tmp_path, monkeypatch):
    cfg = _cfg()
    monkeypatch.delenv("KORTEX_ISSUE1_API_KEY", raising=False)
    with pytest.raises(ErroOrcamento, match="credencial omniroute ausente"):
        compor_orcamento_omniroute(cfg, tmp_path)

    monkeypatch.setenv("KORTEX_ISSUE1_API_KEY", "segredo")
    agora = PRICING_CAPTURADO_EM + PRICING_MAX_AGE_S + 1
    cfg["fx"]["capturado_em"] = agora
    with pytest.raises(ErroOrcamento, match="snapshot pricing vencido"):
        compor_orcamento_omniroute(cfg, tmp_path, relogio=lambda: agora)


def test_N2_declaracao_ignora_pricing_vencido_sem_escrever_brl(tmp_path, monkeypatch):
    cfg = _cfg()
    cfg["sem_contencao_monetaria"] = True
    cfg["omniroute"] = {
        "base_url": cfg["omniroute"]["base_url"],
        "sem_credencial": True,
        "papeis": cfg["omniroute"]["papeis"],
    }
    deps = compor_orcamento_omniroute(
        cfg, tmp_path, relogio=lambda: 1 + PRICING_MAX_AGE_S + 1,
        transporte=lambda *_args: _resposta(),
    )
    adaptador = deps.fabrica(
        "executor", "prompt", 1, RequisitosTentativaCusteada(),
    )[0].adaptador

    assert adaptador.tentar_uma_vez_sem_medicao() == "resposta sem medicao"
    assert list(tmp_path.rglob("*.sqlite3")) == []


def test_N3_declaracao_emite_evento_de_medicao_desligada(tmp_path, monkeypatch):
    cfg = _cfg()
    cfg["sem_contencao_monetaria"] = True
    cfg["omniroute"] = {
        "base_url": cfg["omniroute"]["base_url"],
        "sem_credencial": True,
        "papeis": cfg["omniroute"]["papeis"],
    }
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps({"versao": "0.1"}), encoding="utf-8")

    log_path = tmp_path / "log.jsonl"
    monkeypatch.setattr(cli, "LogEventos", lambda _path: LogEventos(log_path))

    class GrafoFake:
        def invoke(self, _entrada, _config):
            return {"resposta_final": "ok"}

    monkeypatch.setattr(cli, "construir_grafo", lambda *_args, **_kwargs: GrafoFake())
    monkeypatch.setattr(cli, "_drenar_orcamento_cli", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        cli.sys, "argv", ["motor", "--modelos", str(cfg_path), "--spec", str(spec_path)],
    )

    assert cli.main() == 0
    eventos = [json.loads(linha) for linha in log_path.read_text().splitlines()]
    declaracao = [evento for evento in eventos if evento["evento"] == "medicao.monetaria_desligada"]
    assert len(declaracao) == 1
    assert declaracao[0]["motivo"] == "operador declarou sem_contencao_monetaria"


def test_N4_desligar_dinheiro_nao_remove_limite_de_tentativas(tmp_path):
    chamadas: list[str] = []

    class TentativaSemMedicao:
        def tentar_uma_vez_sem_medicao(self) -> str:
            chamadas.append("tentativa")
            return ""

    def fabrica(papel, _prompt, _tentativa, _requisitos):
        if papel == "pesquisador":
            return [RotaTentativaCusteada("rota", "provedor", TentativaSemMedicao())]
        return []

    spec = json.loads(
        (Path(__file__).parent.parent / "exemplos" / "missao-pesquisa.json").read_text()
    )
    spec["subagentes"] = [spec["subagentes"][0]]
    spec["restricoes"]["max_tentativas"] = 2
    log = LogEventos(tmp_path / "log.jsonl")
    try:
        grafo = construir_grafo(
            ClienteStub(lambda *_args: "nao deve usar cliente legado"), log,
            politica=PoliticaGates(overrides={"plano": "prosseguir"}),
            repositorio_orcamento=None,
            medicao_monetaria_desligada=True,
            fabrica_tentativas_orcadas=fabrica,
            teto_bootstrap=TETO_OPERADOR_TESTE,
        )
        grafo.invoke({"spec": spec, "run_id": "issue1", "thread_id": "issue1"})
    finally:
        log.fechar()

    assert len(chamadas) == 2


@pytest.mark.parametrize(
    ("fabrica", "repositorio", "medicao", "motivo"),
    [
        (None, object(), False, "fabrica de adaptadores custeados ausente"),
        (
            lambda *_args: [RotaTentativaCusteada("rota", "provedor", object())],
            None, False, "repositorio de orcamento ausente",
        ),
        (lambda *_args: [], None, "sim", "medicao monetaria invalida"),
        (lambda *_args: [], None, 1, "medicao monetaria invalida"),
    ],
    ids=["sem-fabrica", "sem-repositorio", "medicao-string", "medicao-int"],
)
def test_guardas_de_orcamento_recusam_antes_de_qualquer_efeito(
    tmp_path, fabrica, repositorio, medicao, motivo,
):
    efeitos: list[str] = []
    cliente = ClienteStub(lambda papel, _prompt: efeitos.append(papel) or "INDEVIDO")
    log = LogEventos(tmp_path / "guardas.jsonl")
    try:
        grafo = construir_grafo(
            cliente, log, checkpointer=InMemorySaver(),
            repositorio_orcamento=repositorio,
            medicao_monetaria_desligada=medicao,
            fabrica_tentativas_orcadas=fabrica,
            teto_bootstrap=TETO_OPERADOR_TESTE,
        )
        with pytest.raises(ErroOrcamento, match=motivo):
            grafo.invoke(
                {"missao_texto": "nao execute", "run_id": "guard", "thread_id": "guard"},
                {"configurable": {"thread_id": "guard"}},
            )
    finally:
        log.fechar()
    assert efeitos == []
