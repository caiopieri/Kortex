import json

import pytest

from motor import composicao_orcamento
from motor.composicao_orcamento import PRICING_CAPTURADO_EM, compor_orcamento_omniroute
from motor.orcamento import ErroOrcamento, RequisitosTentativaCusteada


_ENV = "KORTEX_ISSUE14_API_KEY"


def _rota(modelo: str, provider_id: str) -> dict[str, object]:
    return {
        "modelo": modelo,
        "provider_id": provider_id,
        "max_input_tokens": 24_000,
        "max_completion_tokens": 4_000,
    }


def _cfg(bloco: dict[str, object]) -> dict[str, object]:
    return {
        "omniroute": bloco,
        "fx": {
            "versao": "fx-teste",
            "capturado_em": PRICING_CAPTURADO_EM,
            "cotacao_venda": "5.20",
        },
        "fx_max_age_s": 86_400,
        "margem": "1.20",
        "teto_bootstrap_brl": "150",
        "timeout": 60,
    }


def _bloco_com_credencial() -> dict[str, object]:
    return {
        "base_url": "http://localhost:20128/v1",
        "api_key_env": _ENV,
        "papeis": {
            "executor": _rota("claude/claude-opus-4-8", "anthropic"),
            "verifier": _rota("agy/gemini-3.1-pro-high", "google"),
        },
    }


def _bloco_sem_credencial() -> dict[str, object]:
    return {
        "base_url": "http://localhost:20128/v1",
        "sem_credencial": True,
        "papeis": {
            "executor": _rota("claude/claude-opus-4-8", "anthropic"),
            "verifier": _rota("agy/gemini-3.1-pro-high", "google"),
        },
    }


def _compor(cfg: dict[str, object], workspace, **kwargs):
    return compor_orcamento_omniroute(
        cfg,
        workspace,
        relogio=lambda: PRICING_CAPTURADO_EM,
        **kwargs,
    )


def test_omniroute_sem_declaracao_de_ausencia_e_sem_variavel_reprova(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.delenv(_ENV, raising=False)

    with pytest.raises(ErroOrcamento, match="credencial omniroute ausente"):
        _compor(_cfg(_bloco_com_credencial()), tmp_path)


def test_omniroute_declarado_sem_credencial_compoe_monta_cadeia_e_nao_le_env(
    tmp_path, monkeypatch,
) -> None:
    leitura_original = composicao_orcamento.os.environ.get

    def get_env(nome, *args):
        if nome == _ENV:
            raise AssertionError("a rota sem credencial nao pode ler ambiente")
        return leitura_original(nome, *args)

    monkeypatch.setattr(composicao_orcamento.os.environ, "get", get_env)

    def transporte(_url, _corpo, cabecalhos, _timeout):
        assert "Authorization" not in cabecalhos
        return (
            200,
            {"X-Request-ID": "req-anon"},
            json.dumps({
                "model": "claude-opus-4-8",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "total_tokens": 2,
                },
            }).encode(),
        )

    deps = _compor(_cfg(_bloco_sem_credencial()), tmp_path, transporte=transporte)
    rota = deps.fabrica(
        "executor", "prompt", 1, RequisitosTentativaCusteada(),
    )[0]

    assert rota.adaptador.tentar_uma_vez().texto == "ok"


def test_omniroute_com_api_key_env_e_variavel_preserva_leitura(
    tmp_path, monkeypatch,
) -> None:
    monkeypatch.setenv(_ENV, "chave-de-teste")

    deps = _compor(_cfg(_bloco_com_credencial()), tmp_path)
    rota = deps.fabrica(
        "executor", "prompt", 1, RequisitosTentativaCusteada(),
    )[0]

    assert rota.adaptador._api_key == "chave-de-teste"
