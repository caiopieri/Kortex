from decimal import Decimal

import pytest

from motor.composicao_orcamento import (
    PRICING_CAPTURADO_EM, PRICING_MAX_AGE_S, ClienteSomenteOrcado,
    compor_orcamento_openai,
)
from motor.modelos import ClienteOpenAICompat
from motor.openai_orcado import PRICING_VERSION
from motor.orcamento import (
    ErroOrcamento, IdentidadeTentativaCusteada, RequisitosTentativaCusteada,
    executar_tentativa_custeada,
)


def _cfg(capturado_em=PRICING_CAPTURADO_EM):
    return {"orcamento_openai": {
        "api_key_env": "OPENAI_API_KEY",
        "capacidades": ["pesquisa", "redacao"],
        "max_completion_tokens": 100,
        "fx": {"versao": "ptax-2026-07-14", "capturado_em": capturado_em,
               "cotacao_venda": "5.50"},
        "fx_max_age_s": 3600,
        "margem": "1.20",
        "timeout": 30,
    }}


def test_config_constroi_somente_adapter_orcado_com_pricing_selado(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "segredo")
    deps = compor_orcamento_openai(
        _cfg(), tmp_path, relogio=lambda: PRICING_CAPTURADO_EM,
    )

    assert isinstance(deps.cliente, ClienteSomenteOrcado)
    assert not isinstance(deps.cliente, ClienteOpenAICompat)
    rota = deps.fabrica(
        "planner", "prompt", 1, RequisitosTentativaCusteada(capacidades=("pesquisa",)),
    )[0]
    cotacao = rota.adaptador.cotar_tentativa()
    assert rota.provider_id == "openai"
    assert cotacao.pricing_version.startswith(
        f"{PRICING_VERSION}@{PRICING_CAPTURADO_EM}+fx:ptax-2026-07-14"
    )
    assert cotacao.maximo > Decimal("0")


def test_snapshot_envelhece_por_tentativa_e_bloqueia_sem_rede(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "segredo")
    posts = []
    agora = PRICING_CAPTURADO_EM + PRICING_MAX_AGE_S + 1
    deps = compor_orcamento_openai(
        _cfg(agora), tmp_path, relogio=lambda: agora,
        transporte=lambda *_: posts.append(True),
    )

    with pytest.raises(ErroOrcamento, match="pricing stale"):
        deps.fabrica("planner", "prompt", 1, RequisitosTentativaCusteada())
    assert posts == []


def test_teto_bootstrap_dois_reais_bloqueia_antes_da_rede(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "segredo")
    posts = []
    deps = compor_orcamento_openai(
        _cfg(), tmp_path, relogio=lambda: PRICING_CAPTURADO_EM,
        transporte=lambda *_: posts.append(True),
    )
    adaptador = deps.fabrica("planner", "p", 1, RequisitosTentativaCusteada())[0].adaptador
    sessao = deps.repositorio.sessao("run", "thread", Decimal("2"))
    resultado = executar_tentativa_custeada(
        deps.repositorio, sessao,
        IdentidadeTentativaCusteada("reserva", "call", "openai", 1), adaptador,
    )

    assert resultado is None and posts == []


def test_provider_e_ferramenta_incompativeis_nao_criam_adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "segredo")
    deps = compor_orcamento_openai(_cfg(), tmp_path, relogio=lambda: PRICING_CAPTURADO_EM)

    assert deps.fabrica(
        "verifier", "p", 1, RequisitosTentativaCusteada(evitar_provedor="openai"),
    ) == []
    assert deps.fabrica(
        "executor", "p", 1, RequisitosTentativaCusteada(ferramentas="web"),
    ) == []
    assert deps.fabrica(
        "executor", "p", 1, RequisitosTentativaCusteada(capacidades=("codigo",)),
    ) == []
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ErroOrcamento, match="credencial"):
        deps.fabrica("planner", "p", 1, RequisitosTentativaCusteada())


@pytest.mark.parametrize("mutacao", ["ausente", "extra", "decimal_float", "env_vazia"])
def test_config_hostil_falha_fechado(tmp_path, monkeypatch, mutacao):
    monkeypatch.setenv("OPENAI_API_KEY", "segredo")
    cfg = _cfg()
    if mutacao == "ausente":
        cfg = {}
    elif mutacao == "extra":
        cfg["orcamento_openai"]["surpresa"] = True
    elif mutacao == "decimal_float":
        cfg["orcamento_openai"]["margem"] = 1.2
    else:
        monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ErroOrcamento):
        compor_orcamento_openai(cfg, tmp_path, relogio=lambda: PRICING_CAPTURADO_EM)
