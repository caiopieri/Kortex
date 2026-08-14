from decimal import Decimal

import pytest

from motor.composicao_orcamento import compor_orcamento_omniroute
from motor.omniroute_orcado import ROTAS_GRATIS_CAPTURADO_EM
from motor.orcamento import (
    ErroOrcamento,
    RequisitosTentativaCusteada,
    RotaTentativaCusteada,
)


_ENV = "KORTEX_TESTE_MOEDA_ROTA"
_PAGA_ANTHROPIC = ("claude/claude-opus-4-8", "anthropic")
_PAGA_GOOGLE = ("agy/gemini-3.1-pro-high", "google")
_GRATIS_META = ("nvidia/meta/llama-3.1-8b-instruct", "meta")
_GRATIS_DEEPSEEK = ("alibaba/deepseek-v3.2", "deepseek")


def _rota(modelo: str, provider_id: str) -> dict[str, object]:
    return {
        "modelo": modelo,
        "provider_id": provider_id,
        "max_input_tokens": 24_000,
        "max_completion_tokens": 4_000,
    }


def _cfg(moedas: set[str]) -> dict[str, object]:
    if moedas == {"BRL"}:
        executor, verifier = _PAGA_ANTHROPIC, _PAGA_GOOGLE
    elif moedas == {"TOKEN"}:
        executor, verifier = _GRATIS_META, _GRATIS_DEEPSEEK
    else:
        executor, verifier = _GRATIS_META, _PAGA_ANTHROPIC
    cfg: dict[str, object] = {
        "omniroute": {
            "base_url": "http://localhost:20128/v1",
            "api_key_env": _ENV,
            "papeis": {
                "executor": _rota(*executor),
                "verifier": _rota(*verifier),
            },
        },
        "fx": {
            "versao": "fx-teste",
            "capturado_em": ROTAS_GRATIS_CAPTURADO_EM,
            "cotacao_venda": "5.20",
        },
        "fx_max_age_s": 86_400,
        "margem": "1.20",
        "timeout": 60,
    }
    if "BRL" in moedas:
        cfg["teto_bootstrap_brl"] = "900.0"
    if "TOKEN" in moedas:
        cfg["teto_bootstrap_token"] = "100000"
    return cfg


@pytest.fixture(autouse=True)
def _credencial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENV, "chave")


def _compor(cfg: dict[str, object], workspace):
    return compor_orcamento_omniroute(
        cfg,
        workspace,
        relogio=lambda: ROTAS_GRATIS_CAPTURADO_EM,
    )


def test_rota_omniroute_carrega_moeda_derivada_do_catalogo(tmp_path) -> None:
    cfg = _cfg({"BRL", "TOKEN"})
    deps = _compor(cfg, tmp_path)

    executor = deps.fabrica(
        "executor", "prompt", 1, RequisitosTentativaCusteada(),
    )[0]
    verifier = deps.fabrica(
        "verifier", "prompt", 1, RequisitosTentativaCusteada(),
    )[0]

    assert (executor.moeda, verifier.moeda) == ("TOKEN", "BRL")
    papeis = cfg["omniroute"]["papeis"]  # type: ignore[index]
    assert all("moeda" not in rota for rota in papeis.values())


@pytest.mark.parametrize(
    ("moedas", "tetos"),
    [
        ({"BRL"}, {"BRL": Decimal("900.0")}),
        ({"TOKEN"}, {"TOKEN": Decimal("100000")}),
        (
            {"BRL", "TOKEN"},
            {"BRL": Decimal("900.0"), "TOKEN": Decimal("100000")},
        ),
    ],
)
def test_orcamentos_e_tetos_seguem_exatamente_as_moedas_usadas(
    tmp_path, moedas: set[str], tetos: dict[str, Decimal],
) -> None:
    deps = _compor(_cfg(moedas), tmp_path)

    assert {
        moeda: orcamento.teto_bootstrap
        for moeda, orcamento in deps.orcamentos.items()
    } == tetos
    assert all(
        orcamento.repositorio.moeda == moeda
        for moeda, orcamento in deps.orcamentos.items()
    )
    assert not (tmp_path / "orcamento" / "orcamento.sqlite3").exists()
    assert not (tmp_path / "orcamento" / "cota.sqlite3").exists()


@pytest.mark.parametrize(
    ("moedas", "campo"),
    [
        ({"BRL"}, "teto_bootstrap_brl"),
        ({"TOKEN"}, "teto_bootstrap_token"),
        ({"BRL", "TOKEN"}, "teto_bootstrap_brl"),
        ({"BRL", "TOKEN"}, "teto_bootstrap_token"),
    ],
)
def test_cada_moeda_usada_exige_seu_teto(
    tmp_path, moedas: set[str], campo: str,
) -> None:
    cfg = _cfg(moedas)
    del cfg[campo]

    with pytest.raises(ErroOrcamento, match=campo):
        _compor(cfg, tmp_path)


@pytest.mark.parametrize("valor", [None, 1, "0", "-1", "1.5", "01"])
def test_teto_token_exige_string_de_inteiro_estritamente_positivo(
    tmp_path, valor: object,
) -> None:
    cfg = _cfg({"TOKEN"})
    cfg["teto_bootstrap_token"] = valor

    with pytest.raises(ErroOrcamento, match="teto_bootstrap_token invalido"):
        _compor(cfg, tmp_path)


def test_rota_injetada_preserva_default_brl_e_recusa_moeda_desconhecida() -> None:
    adaptador = object()
    assert RotaTentativaCusteada(  # type: ignore[arg-type]
        "rota", "provider", adaptador,
    ).moeda == "BRL"
    with pytest.raises(ErroOrcamento, match="identidade de rota custeada invalida"):
        RotaTentativaCusteada(  # type: ignore[arg-type]
            "rota", "provider", adaptador, moeda="USD",  # type: ignore[arg-type]
        )
