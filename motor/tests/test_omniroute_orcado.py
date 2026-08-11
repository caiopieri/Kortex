"""Adaptador e composição via OmniRoute.

Estes testes existem porque cada um deles corresponde a um defeito que derrubou
uma missão real em 2026-07-28. Não são hipotéticos.
"""
from __future__ import annotations

import json
import time
from decimal import Decimal

import pytest

from motor.composicao_orcamento import (
    compor_orcamento_omniroute,
    validar_independencia_orcada,
)
from motor.omniroute_orcado import (
    MAX_INPUT_TOKENS,
    PRECOS,
    PRICING_SOURCE,
    PRICING_VERSION,
    ClienteOmniRouteCusteado,
    SnapshotFX,
    SnapshotPricing,
)
from motor.orcamento import ErroOrcamento, RequisitosTentativaCusteada

_MODELO = "claude/claude-opus-4-8"
_ENV = "KORTEX_TESTE_OMNIROUTE"


def _resposta(*, model=_MODELO.split("/")[-1], prompt=100, completion=10,
              total=110, extras=None):
    corpo = {
        "model": model,
        "choices": [{"message": {"content": "ok"}}],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            **(extras or {}),
        },
    }
    return 200, {"X-Request-ID": "req_1"}, json.dumps(corpo).encode()


def _cliente(transporte, *, modelo=_MODELO, **kw):
    agora = kw.pop("agora", 1000)
    return ClienteOmniRouteCusteado(
        api_key="k", base_url="http://localhost:20128/v1", modelo=modelo,
        prompt="p", max_input_tokens=kw.pop("max_input_tokens", 24000),
        max_completion_tokens=kw.pop("max_completion_tokens", 4000),
        fx=SnapshotFX("fx", 900, Decimal("5")),
        pricing=SnapshotPricing(PRICING_VERSION, 900, PRICING_SOURCE),
        agora=agora, fx_max_age_s=200, pricing_max_age_s=200,
        margem=Decimal("1.10"), timeout=60, transporte=transporte, **kw,
    )


# --------------------------------------------------------------------------
# Tokens de raciocínio — o defeito que reprovou o verifier em toda missão
# --------------------------------------------------------------------------

def test_tokens_de_raciocinio_entram_como_saida() -> None:
    """Gemini conta "pensamento" no total mas NÃO em `completion_tokens`.

    Observado ao vivo: prompt=2083, completion=1, total=2254. A checagem estrita
    `total == entrada + saida`, copiada do adapter da OpenAI, reprovava TODA
    resposta desses modelos — e ignorar o resíduo subfaturaria a linha mais cara,
    porque o provedor cobra pensamento como saída.
    """
    from motor.omniroute_orcado import _arredondar_brl

    cliente = _cliente(lambda *_: _resposta(prompt=2083, completion=1, total=2254))
    resultado = cliente.tentar_uma_vez()

    preco = PRECOS[_MODELO]
    residuo = 2254 - 2083 - 1  # 170 tokens de pensamento
    esperado = _arredondar_brl(
        (Decimal(2083) * preco.entrada / Decimal(1_000_000)
         + Decimal(1 + residuo) * preco.saida / Decimal(1_000_000))
        * Decimal("5")  # cotação do fixture; margem não entra no custo real
    )
    assert resultado.custo_real == esperado

    # E o essencial: ignorar o resíduo custaria menos, ou seja, subfaturaria.
    sem_residuo = _arredondar_brl(
        (Decimal(2083) * preco.entrada / Decimal(1_000_000)
         + Decimal(1) * preco.saida / Decimal(1_000_000)) * Decimal("5")
    )
    assert resultado.custo_real > sem_residuo


def test_reasoning_tokens_declarado_tambem_e_cobrado() -> None:
    cliente = _cliente(lambda *_: _resposta(
        prompt=100, completion=10, total=110,
        extras={"completion_tokens_details": {"reasoning_tokens": 40}},
    ))
    barato = _cliente(lambda *_: _resposta(prompt=100, completion=10, total=110))
    assert cliente.tentar_uma_vez().custo_real > barato.tentar_uma_vez().custo_real


def test_total_menor_que_as_partes_continua_reprovando() -> None:
    """A tolerância é só para o resíduo POSITIVO. Total abaixo da soma é usage
    corrompido e tem que falhar fechado, senão o custeio aceita qualquer coisa."""
    cliente = _cliente(lambda *_: _resposta(prompt=100, completion=10, total=50))
    with pytest.raises(ErroOrcamento, match="usage inconsistente"):
        cliente.tentar_uma_vez()


# --------------------------------------------------------------------------
# Fronteira do adaptador
# --------------------------------------------------------------------------

def test_modelo_sem_preco_declarado_nao_roda() -> None:
    """Fail-closed: executar com custo desconhecido é pior que não executar."""
    with pytest.raises(ErroOrcamento, match="sem preco declarado"):
        _cliente(lambda *_: _resposta(), modelo="inventado/modelo-x")


def test_stream_false_e_obrigatorio_no_payload() -> None:
    """Sem isso o proxy responde SSE mesmo sem pedir stream, e o corpo deixa de
    ser JSON parseável."""
    visto: dict = {}

    def transporte(url, corpo, headers, timeout):
        visto.update(json.loads(corpo))
        return _resposta()

    _cliente(transporte).tentar_uma_vez()
    assert visto["stream"] is False
    assert visto["model"] == _MODELO


def test_modelo_ecoado_sem_prefixo_do_gateway_e_aceito() -> None:
    """O proxy devolve `claude-opus-4-8` para `claude/claude-opus-4-8`.
    Igualdade estrita reprovaria toda resposta."""
    _cliente(lambda *_: _resposta(model="claude-opus-4-8")).tentar_uma_vez()


def test_modelo_realmente_divergente_reprova() -> None:
    with pytest.raises(ErroOrcamento, match="modelo divergente"):
        _cliente(lambda *_: _resposta(model="outro-modelo")).tentar_uma_vez()


def test_erro_do_upstream_no_corpo_com_http_200_reprova() -> None:
    def transporte(*_):
        return 200, {"X-Request-ID": "r"}, json.dumps(
            {"error": {"message": "No active credentials for provider: openrouter"}}
        ).encode()

    with pytest.raises(ErroOrcamento, match="upstream do OmniRoute recusou"):
        _cliente(transporte).tentar_uma_vez()


def test_max_input_tokens_e_configuravel_mas_limitado() -> None:
    """Configurável porque a reserva é pelo pior caso: fixar em 200k faz cada
    tentativa reservar ~40x o que um prompt real consome, e o teto barra missão
    legítima. Continua sendo teto."""
    _cliente(lambda *_: _resposta(), max_input_tokens=8000)
    with pytest.raises(ErroOrcamento, match="limites de token invalidos"):
        _cliente(lambda *_: _resposta(), max_input_tokens=MAX_INPUT_TOKENS + 1)


# --------------------------------------------------------------------------
# Composição: preferência ordenada por papel
# --------------------------------------------------------------------------

def _cfg() -> dict:
    def rota(modelo, provider):
        return {
            "modelo": modelo, "provider_id": provider,
            "max_input_tokens": 24000, "max_completion_tokens": 4000,
        }

    return {
        "omniroute": {
            "base_url": "http://localhost:20128/v1",
            "api_key_env": _ENV,
            "papeis": {
                "planner": [rota("claude/claude-opus-4-8", "anthropic")],
                "executor": [
                    rota("claude/claude-opus-4-8", "anthropic"),
                    rota("agy/gemini-3.1-pro-high", "google"),
                ],
                "verifier": [
                    rota("agy/gemini-3.1-pro-high", "google"),
                    rota("claude/claude-opus-4-6", "anthropic"),
                ],
            },
        },
        "fx": {
            "versao": "fx", "capturado_em": int(time.time()),
            "cotacao_venda": "5.1271",
        },
        "fx_max_age_s": 86400,
        "margem": "1.20",
        "teto_bootstrap_brl": "900.0",
        "timeout": 300,
    }


@pytest.fixture
def credencial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(_ENV, "chave")


def test_papel_com_uma_alternativa_so_fica_sem_rota_quando_o_produtor_coincide(
    credencial, tmp_path
) -> None:
    """O defeito que derrubou duas missões inteiras.

    O motor passa `evitar_provedor` com quem PRODUZIU o nó. Com Anthropic
    planejando, um verifier exclusivamente Anthropic nunca roda — e a falha
    aparece como "falha externa do verifier", que não explica nada.
    """
    cfg = _cfg()
    cfg["omniroute"]["papeis"]["verifier"] = [
        cfg["omniroute"]["papeis"]["verifier"][1]  # só a anthropic
    ]
    deps = compor_orcamento_omniroute(cfg, tmp_path)
    assert deps.fabrica(
        "verifier", "p", 1, RequisitosTentativaCusteada(evitar_provedor="anthropic")
    ) == []


def test_alternativa_assume_quando_a_preferida_e_evitada(credencial, tmp_path) -> None:
    deps = compor_orcamento_omniroute(_cfg(), tmp_path)
    assert deps.fabrica("verifier", "p", 1, RequisitosTentativaCusteada())[
        0
    ].provider_id == "google"
    assert deps.fabrica(
        "verifier", "p", 1, RequisitosTentativaCusteada(evitar_provedor="google")
    )[0].provider_id == "anthropic"
    assert deps.fabrica(
        "executor", "p", 1, RequisitosTentativaCusteada(evitar_provedor="anthropic")
    )[0].provider_id == "google"


def test_independencia_passa_com_alternativas(credencial, tmp_path) -> None:
    validar_independencia_orcada(
        compor_orcamento_omniroute(_cfg(), tmp_path).rotas_certificadas
    )


def test_modelo_sem_preco_na_config_recusa_a_composicao(credencial, tmp_path) -> None:
    cfg = _cfg()
    cfg["omniroute"]["papeis"]["executor"][0]["modelo"] = "inventado/x"
    with pytest.raises(ErroOrcamento, match="sem preco declarado"):
        compor_orcamento_omniroute(cfg, tmp_path)


def test_credencial_ausente_recusa(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv(_ENV, raising=False)
    with pytest.raises(ErroOrcamento, match="credencial omniroute ausente"):
        compor_orcamento_omniroute(_cfg(), tmp_path)


def test_executor_ou_verifier_ausente_recusa(credencial, tmp_path) -> None:
    cfg = _cfg()
    del cfg["omniroute"]["papeis"]["verifier"]
    with pytest.raises(ErroOrcamento, match="papel verifier ausente"):
        compor_orcamento_omniroute(cfg, tmp_path)


def test_a_cadeia_inteira_e_devolvida_para_o_motor_poder_cair_na_proxima(
    credencial, tmp_path
) -> None:
    """`chamar_orcado` percorre a lista de rotas em ordem e cai na próxima
    quando uma falha. Devolver só a preferida jogava esse failover fora: bastava
    o provedor de topo estar sem cota para o papel inteiro morrer com
    "modelo não respondeu" — foi o que derrubou uma missão real.
    """
    deps = compor_orcamento_omniroute(_cfg(), tmp_path)
    rotas = deps.fabrica("verifier", "p", 1, RequisitosTentativaCusteada())
    assert [r.provider_id for r in rotas] == ["google", "anthropic"]

    # `evitar_provedor` continua podando a cadeia, não só a primeira posição.
    podada = deps.fabrica(
        "verifier", "p", 1, RequisitosTentativaCusteada(evitar_provedor="google")
    )
    assert [r.provider_id for r in podada] == ["anthropic"]


def test_provider_id_que_contradiz_o_vendor_do_modelo_recusa(credencial, tmp_path) -> None:
    """O mesmo modelo e servido por assinaturas diferentes: `claude/claude-opus-4-6`
    e `agy/claude-opus-4-6-thinking` sao o MESMO Opus 4.6, muda so quem paga.

    Declarar a rota `agy/` como "google" faria executor e verifier passarem na
    independencia sendo o mesmo modelo -- dois julgamentos que erram identico
    contados como dois. O vendor e code-owned; a config nao pode contradize-lo.
    """
    cfg = _cfg()
    cfg["omniroute"]["papeis"]["verifier"] = [{
        "modelo": "agy/claude-opus-4-6-thinking", "provider_id": "google",
        "max_input_tokens": 24000, "max_completion_tokens": 4000,
    }]
    with pytest.raises(ErroOrcamento, match="contradiz o vendor"):
        compor_orcamento_omniroute(cfg, tmp_path)


def test_todo_modelo_precificado_declara_vendor_conhecido() -> None:
    """Vendor errado nao quebra nada visivelmente -- so afrouxa a independencia
    em silencio. Por isso o conjunto e fechado e conferido aqui."""
    assert {p.vendor for p in PRECOS.values()} <= {"anthropic", "google", "openai"}


def test_config_de_producao_passa_na_independencia(credencial, tmp_path) -> None:
    """A config versionada em exemplos/ e o que roda missao de verdade. Se ela
    parar de compor, o motor nao arranca -- e melhor descobrir no gate."""
    import json as _json
    from pathlib import Path as _Path

    cfg = _json.loads(
        (_Path(__file__).resolve().parents[1] / "exemplos" / "cfg-omniroute.json")
        .read_text(encoding="utf-8")
    )
    cfg["omniroute"]["api_key_env"] = _ENV
    cfg["fx"]["capturado_em"] = int(time.time())
    deps = compor_orcamento_omniroute(cfg, tmp_path)
    validar_independencia_orcada(deps.rotas_certificadas)

    # E o essencial para o failover: nenhum papel pode ficar sem rota quando o
    # produtor do no coincide com a primeira alternativa.
    for papel in ("executor", "verifier", "evaluator", "synthesizer", "planner"):
        for evitado in ("anthropic", "openai", "google"):
            assert deps.fabrica(
                papel, "p", 1, RequisitosTentativaCusteada(evitar_provedor=evitado)
            ), f"{papel} fica sem rota evitando {evitado}"


def test_route_ids_da_cadeia_sao_distintos(credencial, tmp_path) -> None:
    """`validar_independencia_orcada` rejeita `route_id` duplicado, e o motor usa
    o índice na cadeia para compor a identidade da reserva."""
    rotas = compor_orcamento_omniroute(_cfg(), tmp_path).fabrica(
        "verifier", "p", 1, RequisitosTentativaCusteada()
    )
    assert len({r.route_id for r in rotas}) == len(rotas)


def test_papel_livre_de_subagente_cai_no_executor(credencial, tmp_path) -> None:
    """`papel` de subagente é campo livre que o planner inventa.

    Descoberto rodando: com `pesquisador`/`redator` na spec gerada, a fábrica
    devolvia [] e TODO subagente morria com "adaptador custeado ausente". Quem a
    certificação governa é o estágio, e subagente é executor por construção.
    """
    deps = compor_orcamento_omniroute(_cfg(), tmp_path)
    rotas = deps.fabrica("pesquisador", "p", 1, RequisitosTentativaCusteada())
    esperadas = deps.fabrica("executor", "p", 1, RequisitosTentativaCusteada())
    assert rotas and [r.provider_id for r in rotas] == [r.provider_id for r in esperadas]


def test_papel_declarado_na_config_nao_cai_no_fallback(credencial, tmp_path) -> None:
    """O fallback não pode atropelar quem o operador declarou explicitamente."""
    cfg = _cfg()
    cfg["omniroute"]["papeis"]["pesquisador"] = [cfg["omniroute"]["papeis"]["verifier"][1]]
    deps = compor_orcamento_omniroute(cfg, tmp_path)
    rotas = deps.fabrica("pesquisador", "p", 1, RequisitosTentativaCusteada())
    assert [r.provider_id for r in rotas] == ["anthropic"]
