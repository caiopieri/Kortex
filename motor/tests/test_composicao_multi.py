"""Composição multi-provedor: o arranjo que destrava produção.

O que estes testes protegem, em ordem de consequência:
  1. o catálogo certificado PASSA em `validar_independencia_orcada` — o
     compositor antigo nunca passou, e era esse o bloqueio de produção;
  2. produtor != juiz vale nos DOIS caminhos, não só no fácil: quando a OpenAI
     executa, ela não pode ser a verifier;
  3. config incompleta ou credencial ausente falha FECHADO.
"""
from __future__ import annotations

import time
from decimal import Decimal

import pytest

from motor.composicao_orcamento import (
    PRICING_CAPTURADO_EM,
    compor_orcamento_multi,
    validar_independencia_orcada,
)
from motor.orcamento import ErroOrcamento, RequisitosTentativaCusteada

_ENVS = {
    "gemini": "KORTEX_TESTE_GEMINI",
    "openai": "KORTEX_TESTE_OPENAI",
    "anthropic": "KORTEX_TESTE_ANTHROPIC",
}


def _cfg(agora: int | None = None) -> dict:
    return {
        "gemini": {
            "api_key_env": _ENVS["gemini"],
            "capacidades": ["redacao", "codigo"],
            "max_completion_tokens": 8000,
        },
        "openai": {
            "api_key_env": _ENVS["openai"],
            "capacidades": ["redacao", "codigo"],
            "max_completion_tokens": 8000,
        },
        "anthropic": {
            "api_key_env": _ENVS["anthropic"],
            "capacidades": ["redacao", "codigo"],
            "max_completion_tokens": 8000,
        },
        "fx": {
            "versao": "ptax-teste",
            "capturado_em": int(time.time()) if agora is None else agora,
            "cotacao_venda": "5.40",
        },
        "fx_max_age_s": 86400,
        "margem": "1.20",
        "teto_bootstrap_brl": "2.0",
        "timeout": 60,
    }


@pytest.fixture
def credenciais(monkeypatch: pytest.MonkeyPatch) -> None:
    for env in _ENVS.values():
        monkeypatch.setenv(env, "chave-de-teste")


def _deps(tmp_path, cfg=None):
    return compor_orcamento_multi(cfg if cfg is not None else _cfg(), tmp_path)


# --------------------------------------------------------------------------
# 1. O bloqueio de produção
# --------------------------------------------------------------------------

def test_catalogo_certificado_passa_na_independencia(credenciais, tmp_path) -> None:
    """O compositor de OpenAI sozinho NUNCA passou aqui — era o bloqueio.

    Uma rota só, `openai` cobrindo executor e verifier, e a validação exige
    provider(executor) != provider(verifier).
    """
    validar_independencia_orcada(_deps(tmp_path).rotas_certificadas)


def test_compositor_openai_sozinho_continua_reprovando(tmp_path, monkeypatch) -> None:
    """Trava do achado: se alguém "consertar" a validação, este teste cai.

    A regra não é burocracia — é o invariante de que produzir e julgar com o
    mesmo provedor não vale.
    """
    from motor.composicao_orcamento import compor_orcamento_openai

    monkeypatch.setenv("KORTEX_TESTE_SO_OPENAI", "chave-de-teste")
    cfg = {
        "orcamento_openai": {
            "api_key_env": "KORTEX_TESTE_SO_OPENAI",
            "capacidades": ["redacao"],
            "max_completion_tokens": 8000,
            "fx": {
                "versao": "ptax-teste",
                "capturado_em": int(time.time()),
                "cotacao_venda": "5.40",
            },
            "fx_max_age_s": 86400,
            "margem": "1.20",
            "teto_bootstrap_brl": "2.0",
            "timeout": 60,
        }
    }
    deps = compor_orcamento_openai(cfg, tmp_path)
    with pytest.raises(ErroOrcamento, match="dois providers certificados"):
        validar_independencia_orcada(deps.rotas_certificadas)


# --------------------------------------------------------------------------
# 2. Produtor != juiz nos dois caminhos
# --------------------------------------------------------------------------

def _rota(deps, papel: str, **kwargs):
    rotas = deps.fabrica(papel, "prompt", 1, RequisitosTentativaCusteada(**kwargs))
    return rotas[0] if rotas else None


def test_mapa_de_papeis_segue_o_desenho_do_fundador(credenciais, tmp_path) -> None:
    deps = compor_orcamento_multi(
        _cfg(PRICING_CAPTURADO_EM), tmp_path, relogio=lambda: PRICING_CAPTURADO_EM,
    )
    assert _rota(deps, "planner").provider_id == "anthropic"
    assert _rota(deps, "executor").provider_id == "google"
    assert _rota(deps, "verifier").provider_id == "openai"
    assert _rota(deps, "evaluator").provider_id == "anthropic"
    assert _rota(deps, "synthesizer").provider_id == "openai"


def test_openai_executando_nao_pode_verificar_a_si_mesma(credenciais, tmp_path) -> None:
    """O caminho de alta complexidade, que é onde a independência quase escapa.

    Gemini fora (evitado), OpenAI executa. Aí o verifier PRECISA sair da
    Anthropic — se voltasse OpenAI, o produtor estaria julgando a própria obra.
    """
    deps = compor_orcamento_multi(
        _cfg(PRICING_CAPTURADO_EM), tmp_path, relogio=lambda: PRICING_CAPTURADO_EM,
    )
    executor = _rota(deps, "executor", evitar_provedor="google")
    assert executor.provider_id == "openai"
    verifier = _rota(deps, "verifier", evitar_provedor="openai")
    assert verifier.provider_id == "anthropic"
    assert verifier.provider_id != executor.provider_id


def test_papel_sem_rota_elegivel_devolve_vazio_em_vez_de_improvisar(
    credenciais, tmp_path
) -> None:
    deps = _deps(tmp_path)
    assert deps.fabrica(
        "planner", "prompt", 1, RequisitosTentativaCusteada(evitar_provedor="anthropic")
    ) == []
    assert deps.fabrica("papel-inexistente", "prompt", 1,
                        RequisitosTentativaCusteada()) == []


def test_capacidade_nao_coberta_derruba_a_rota(credenciais, tmp_path) -> None:
    deps = _deps(tmp_path)
    assert deps.fabrica(
        "executor", "prompt", 1,
        RequisitosTentativaCusteada(capacidades=("visao",)),
    ) == []


def test_ferramentas_nao_sao_roteaveis_por_este_arranjo(credenciais, tmp_path) -> None:
    deps = _deps(tmp_path)
    assert deps.fabrica(
        "executor", "prompt", 1, RequisitosTentativaCusteada(ferramentas="busca"),
    ) == []


# --------------------------------------------------------------------------
# 3. Fail-closed
# --------------------------------------------------------------------------

def test_credencial_ausente_recusa_a_composicao(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv(_ENVS["gemini"], "chave-de-teste")
    monkeypatch.setenv(_ENVS["openai"], "chave-de-teste")
    monkeypatch.delenv(_ENVS["anthropic"], raising=False)
    with pytest.raises(ErroOrcamento, match="credencial anthropic ausente"):
        _deps(tmp_path)


@pytest.mark.parametrize(
    "chave", ["gemini", "openai", "anthropic", "fx", "margem", "teto_bootstrap_brl"]
)
def test_config_incompleta_recusa(credenciais, tmp_path, chave: str) -> None:
    cfg = _cfg()
    del cfg[chave]
    with pytest.raises(ErroOrcamento):
        _deps(tmp_path, cfg)


def test_bloco_de_provedor_com_campo_extra_recusa(credenciais, tmp_path) -> None:
    """`set(bloco) != esperados` e não `>=`: campo a mais é config que o motor
    não entende, e seguir com ela é decidir por conta própria o que ela queria."""
    cfg = _cfg()
    cfg["gemini"]["modelo"] = "gemini-3-pro"
    with pytest.raises(ErroOrcamento, match="bloco gemini ausente ou invalido"):
        _deps(tmp_path, cfg)


def test_fx_stale_derruba_a_tentativa(credenciais, tmp_path) -> None:
    cfg = _cfg()
    cfg["fx"]["capturado_em"] = int(time.time()) - 86400 * 3
    deps = compor_orcamento_multi(cfg, tmp_path)
    with pytest.raises(ErroOrcamento, match="FX stale"):
        _rota(deps, "executor")


def test_teto_bootstrap_chega_intacto(credenciais, tmp_path) -> None:
    assert _deps(tmp_path).teto_bootstrap == Decimal("2.0")


def test_cliente_do_arranjo_recusa_chamada_direta(credenciais, tmp_path) -> None:
    """K-invariante: fora do ledger não se chama modelo."""
    with pytest.raises(ErroOrcamento, match="nao orcado"):
        _deps(tmp_path).cliente.chamar("executor", "prompt")


# --------------------------------------------------------------------------
# 4. Despacho da CLI: presenca POSITIVA elege, ausencia nao
# --------------------------------------------------------------------------

def test_cli_so_elege_o_multi_quando_os_blocos_estao_presentes() -> None:
    """Trava de regressao.

    A primeira versao deste despacho usava "sem `orcamento_openai` -> multi", e
    isso sequestrou toda config que nao tinha bloco nenhum: oito testes de CLI
    passaram a falhar com a mensagem errada. Ausencia nao pode eleger arranjo --
    config sem bloco tem que continuar caindo no compositor antigo e falhando
    com o erro dele.
    """
    import inspect

    import motor.__main__ as principal

    fonte = inspect.getsource(principal.main)
    assert "compor_orcamento_multi" in fonte, "despacho sumiu"
    assert '{"gemini", "anthropic"} <= set(' in fonte, (
        "o multi tem que ser eleito por presenca dos blocos, nao por ausencia de outro"
    )
