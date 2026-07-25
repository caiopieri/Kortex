import json
import sqlite3
from decimal import Decimal

import pytest

from motor.openai_orcado import (
    MAX_INPUT_TOKENS, PRICING_SOURCE, PRICING_VERSION, ClienteOpenAICusteado, MODELO,
    SnapshotFX, SnapshotPricing,
)
from motor.orcamento import (
    ErroOrcamento, IdentidadeTentativaCusteada, RepositorioOrcamento,
    executar_tentativa_custeada,
)


def _resposta(*, model=MODELO, prompt=100, cached=0, completion=10, total=110):
    return 200, {"X-Request-ID": "req_123"}, json.dumps({
        "model": model,
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion,
                  "total_tokens": total, "prompt_tokens_details": {"cached_tokens": cached}},
    }).encode()


def _cliente(transporte, **kw):
    pricing = kw.pop("pricing", SnapshotPricing(PRICING_VERSION, 900, PRICING_SOURCE))
    return ClienteOpenAICusteado(
        api_key="secret", prompt="p", max_input_tokens=MAX_INPUT_TOKENS,
        max_completion_tokens=10, fx=SnapshotFX("ptax-1", 900, Decimal("5")),
        pricing=pricing,
        agora=1000, fx_max_age_s=200, pricing_max_age_s=200,
        margem=Decimal("1.10"), timeout=3,
        transporte=transporte, **kw,
    )


def _executar(tmp_path, cliente):
    repo = RepositorioOrcamento(tmp_path)
    sessao = repo.sessao("run", "thread", Decimal("10"))
    identidade = IdentidadeTentativaCusteada("res", "call", "openai", 1)
    return repo, executar_tentativa_custeada(repo, sessao, identidade, cliente)


def _estado(repo):
    with sqlite3.connect(repo.caminho("run")) as con:
        return con.execute("SELECT maximo,real,status FROM budget_reservation").fetchone()


def test_reserva_usa_pior_caso_nao_cached_e_arredonda_para_cima(tmp_path):
    visto = {}
    def transporte(url, corpo, headers, timeout):
        visto.update(json.loads(corpo))
        return _resposta(cached=50)
    repo, resultado = _executar(tmp_path, _cliente(transporte))
    maximo, real, status = _estado(repo)
    assert set(visto) == {"model", "messages", "max_completion_tokens"}
    assert visto["model"] == MODELO and visto["max_completion_tokens"] == 10
    assert Decimal(maximo) == Decimal("2.750550") > Decimal(real) > 0
    assert status == "RECONCILED" and resultado.usage_ref == "req_123"


def test_fx_stale_bloqueia_antes_de_transporte():
    with pytest.raises(ErroOrcamento, match="stale"):
        ClienteOpenAICusteado(
            api_key="x", prompt="p", max_input_tokens=MAX_INPUT_TOKENS, max_completion_tokens=1,
            fx=SnapshotFX("fx", 1, Decimal("5")), agora=100, fx_max_age_s=10,
            pricing=SnapshotPricing(PRICING_VERSION, 100, PRICING_SOURCE),
            pricing_max_age_s=10,
            margem=Decimal("1"), timeout=1,
        )


def test_pricing_stale_ou_prompt_sem_limite_bloqueia_antes_do_transporte():
    with pytest.raises(ErroOrcamento, match="pricing stale"):
        _cliente(lambda *_: None, pricing=SnapshotPricing(PRICING_VERSION, 1, PRICING_SOURCE))
    with pytest.raises(ErroOrcamento, match="prompt excede"):
        ClienteOpenAICusteado(
            api_key="x", prompt="x" * (MAX_INPUT_TOKENS + 1),
            max_input_tokens=MAX_INPUT_TOKENS, max_completion_tokens=1,
            fx=SnapshotFX("fx", 100, Decimal("5")),
            pricing=SnapshotPricing(PRICING_VERSION, 100, PRICING_SOURCE),
            agora=100, fx_max_age_s=10, pricing_max_age_s=10,
            margem=Decimal("1"), timeout=1,
        )


@pytest.mark.parametrize("resposta", [
    _resposta(model="gpt-5-other"),
    _resposta(prompt=True),
    _resposta(cached=101),
    _resposta(total=999),
    _resposta(prompt=MAX_INPUT_TOKENS + 1, total=MAX_INPUT_TOKENS + 11),
    _resposta(completion=11, total=111),
])
def test_resposta_divergente_ou_usage_invalido_vira_unknown_cost(tmp_path, resposta):
    repo, resultado = _executar(tmp_path, _cliente(lambda *_: resposta))
    assert resultado is None
    maximo, real, status = _estado(repo)
    assert Decimal(maximo) > 0 and real is None and status == "UNKNOWN_COST"


def test_erro_apos_envio_mantem_reserva_e_invalida_sessao(tmp_path):
    chamadas = 0
    def falha(*_):
        nonlocal chamadas
        chamadas += 1
        raise TimeoutError("depois do envio")
    repo, resultado = _executar(tmp_path, _cliente(falha))
    assert chamadas == 1 and resultado is None
    maximo, real, status = _estado(repo)
    assert Decimal(maximo) > 0 and real is None and status == "UNKNOWN_COST"
    assert repo.sessao("run", "thread", Decimal("10")).status == "INVALIDATED"
