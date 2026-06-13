"""Testes do roteamento multi-provider (ClienteRoteador, pronto) e
testes-CONTRATO do ClienteOpenAICompat (T5 — fabricação DeepSeek).

Os testes do contrato ficam em skip enquanto a classe não existe.
Quando o T5 implementar `ClienteOpenAICompat` em motor/modelos.py,
eles ativam sozinhos e são o DoD: NUNCA ajustar o teste à implementação.
"""
from __future__ import annotations

import pytest

from motor import modelos
from motor.modelos import ClienteRoteador, ClienteStub


class FakeLog:
    def __init__(self):
        self.eventos: list[tuple[str, dict]] = []

    def evento(self, tipo: str, **dados):
        self.eventos.append((tipo, dados))

    def tipos(self) -> list[str]:
        return [t for t, _ in self.eventos]


# ---------------------------------------------------------------- roteador

def _stub(resposta):
    return ClienteStub(lambda papel, prompt: resposta)


def test_roteador_papel_mapeado_vai_ao_barato():
    barato, padrao = _stub("do-barato"), _stub("do-claude")
    r = ClienteRoteador(padrao=padrao, mapa={"redator": barato})
    assert r.chamar("redator", "p") == "do-barato"
    assert len(barato.chamadas) == 1 and len(padrao.chamadas) == 0


def test_roteador_papel_fora_do_mapa_vai_ao_padrao():
    barato, padrao = _stub("do-barato"), _stub("do-claude")
    r = ClienteRoteador(padrao=padrao, mapa={"redator": barato})
    assert r.chamar("verifier", "p") == "do-claude"
    assert len(barato.chamadas) == 0


def test_roteador_ferramentas_forca_padrao_sem_tentar_barato():
    barato, padrao = _stub("do-barato"), _stub("do-claude")
    barato.suporta_ferramentas = False
    log = FakeLog()
    r = ClienteRoteador(padrao=padrao, mapa={"pesquisador": barato}, log=log)
    assert r.chamar("pesquisador", "p", ferramentas="WebSearch") == "do-claude"
    assert len(barato.chamadas) == 0
    assert "modelo.roteado_ferramentas" in log.tipos()


def test_roteador_fallback_quando_barato_devolve_none():
    barato, padrao = _stub(None), _stub("do-claude")
    log = FakeLog()
    r = ClienteRoteador(padrao=padrao, mapa={"redator": barato}, log=log)
    assert r.chamar("redator", "p") == "do-claude"
    assert "modelo.fallback" in log.tipos()


def test_roteador_padrao_none_nao_entra_em_loop():
    padrao = _stub(None)
    r = ClienteRoteador(padrao=padrao)
    assert r.chamar("redator", "p") is None
    assert len(padrao.chamadas) == 1


# ------------------------------------------- contrato ClienteOpenAICompat (T5)

OpenAICompat = getattr(modelos, "ClienteOpenAICompat", None)
t5 = pytest.mark.skipif(OpenAICompat is None,
                        reason="T5 pendente — ClienteOpenAICompat ainda não fabricado")


def _resposta_ok(conteudo="olá"):
    return {"choices": [{"message": {"role": "assistant", "content": conteudo}}]}


def _cliente(monkeypatch, respostas, **kw):
    """Cliente com transporte mockado: `respostas` é lista de dict (sucesso)
    ou Exception (falha transiente). Captura payloads enviados."""
    kw.setdefault("base_url", "https://integrate.api.nvidia.com/v1")
    kw.setdefault("api_key", "nvapi-teste")
    kw.setdefault("modelo", "deepseek-ai/deepseek-v4")
    kw.setdefault("backoff", 0)
    c = OpenAICompat(**kw)
    enviados: list[dict] = []
    fila = list(respostas)

    def fake_post(payload, timeout):
        enviados.append(payload)
        r = fila.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(c, "_post", fake_post)
    return c, enviados


@t5
def test_compat_sucesso_devolve_conteudo_limpo(monkeypatch):
    c, enviados = _cliente(monkeypatch, [_resposta_ok("  texto  ")])
    assert c.chamar("redator", "escreva X") == "texto"
    p = enviados[0]
    assert p["model"] == "deepseek-ai/deepseek-v4"
    assert p["messages"] == [{"role": "user", "content": "escreva X"}]


@t5
def test_compat_mapa_papeis_escolhe_modelo(monkeypatch):
    c, enviados = _cliente(monkeypatch, [_resposta_ok()],
                           mapa_papeis={"redator": "moonshotai/kimi-k2.6"})
    c.chamar("redator", "p")
    assert enviados[0]["model"] == "moonshotai/kimi-k2.6"


@t5
def test_compat_nao_suporta_ferramentas(monkeypatch):
    c, enviados = _cliente(monkeypatch, [_resposta_ok()])
    assert c.suporta_ferramentas is False
    assert c.chamar("pesquisador", "p", ferramentas="WebSearch") is None
    assert enviados == []  # não pode nem tentar


@t5
def test_compat_retry_em_falha_transiente(monkeypatch):
    log = FakeLog()
    c, enviados = _cliente(monkeypatch, [OSError("rede"), _resposta_ok("ok")], log=log)
    assert c.chamar("redator", "p") == "ok"
    assert len(enviados) == 2
    assert log.tipos().count("modelo.falha") == 1


@t5
def test_compat_resposta_vazia_e_transiente(monkeypatch):
    c, enviados = _cliente(monkeypatch, [_resposta_ok("   "), _resposta_ok("ok")])
    assert c.chamar("redator", "p") == "ok"
    assert len(enviados) == 2


@t5
def test_compat_falha_total_devolve_none(monkeypatch):
    log = FakeLog()
    c, enviados = _cliente(monkeypatch, [OSError("a"), OSError("b"), OSError("c")],
                           log=log, tentativas=3)
    assert c.chamar("redator", "p") is None
    assert len(enviados) == 3
    assert log.tipos().count("modelo.falha") == 3


@t5
def test_compat_integra_com_roteador(monkeypatch):
    c, _ = _cliente(monkeypatch, [_resposta_ok("do-deepseek")])
    padrao = _stub("do-claude")
    r = ClienteRoteador(padrao=padrao, mapa={"redator": c})
    assert r.chamar("redator", "p") == "do-deepseek"
    # ferramentas → desvia ao padrão por suporta_ferramentas=False
    assert r.chamar("redator", "p", ferramentas="WebSearch") == "do-claude"


# ------------------------------------------------------------ cliente_de_config

def test_config_monta_roteador_com_papeis_baratos(monkeypatch):
    from motor.modelos import ClienteOpenAICompat, cliente_de_config
    monkeypatch.setenv("CHAVE_TESTE", "nvapi-x")
    cfg = {"base_url": "https://x/v1", "api_key_env": "CHAVE_TESTE",
           "modelo": "deepseek-ai/deepseek-v4", "papeis_baratos": ["redator"]}
    r = cliente_de_config(cfg)
    assert isinstance(r, ClienteRoteador)
    assert set(r.mapa) == {"redator"}
    assert isinstance(r.mapa["redator"], ClienteOpenAICompat)
    assert "verifier" not in r.mapa  # julgamento não rebaixa por default


def test_config_sem_chave_no_ambiente_falha_cedo(monkeypatch):
    from motor.modelos import cliente_de_config
    monkeypatch.delenv("CHAVE_AUSENTE", raising=False)
    cfg = {"base_url": "https://x/v1", "api_key_env": "CHAVE_AUSENTE",
           "modelo": "m", "papeis_baratos": []}
    with pytest.raises(ValueError):
        cliente_de_config(cfg)


def test_config_multi_plataforma(monkeypatch):
    from motor.modelos import ClienteOpenAICompat, cliente_de_config
    monkeypatch.setenv("K_NVIDIA", "a")
    monkeypatch.setenv("K_OPENROUTER", "b")
    cfg = {"provedores": {
               "nvidia": {"base_url": "https://nv/v1", "api_key_env": "K_NVIDIA"},
               "openrouter": {"base_url": "https://or/v1", "api_key_env": "K_OPENROUTER"}},
           "papeis": {"redator": "nvidia/deepseek-ai/deepseek-v4",
                      "critico": "nvidia/moonshotai/kimi-k2.6",
                      "synthesizer": "openrouter/qwen/qwen3-coder"}}
    r = cliente_de_config(cfg)
    assert set(r.mapa) == {"redator", "critico", "synthesizer"}
    # mesmo provedor compartilha cliente; modelo certo por papel
    assert r.mapa["redator"] is r.mapa["critico"]
    assert r.mapa["redator"] is not r.mapa["synthesizer"]
    assert r.mapa["redator"].mapa_papeis == {"redator": "deepseek-ai/deepseek-v4",
                                             "critico": "moonshotai/kimi-k2.6"}
    assert r.mapa["synthesizer"].base_url == "https://or/v1"
    assert isinstance(r.mapa["synthesizer"], ClienteOpenAICompat)


def test_config_multi_destino_invalido_falha_cedo(monkeypatch):
    from motor.modelos import cliente_de_config
    monkeypatch.setenv("K1", "x")
    cfg = {"provedores": {"nvidia": {"base_url": "https://nv/v1", "api_key_env": "K1"}},
           "papeis": {"redator": "inexistente/modelo-x"}}
    with pytest.raises(ValueError):
        cliente_de_config(cfg)


def test_config_multi_so_exige_chave_de_provedor_usado(monkeypatch):
    from motor.modelos import cliente_de_config
    monkeypatch.setenv("K_USADO", "x")
    monkeypatch.delenv("K_NAO_USADO", raising=False)
    cfg = {"provedores": {
               "usado": {"base_url": "https://u/v1", "api_key_env": "K_USADO"},
               "ocioso": {"base_url": "https://o/v1", "api_key_env": "K_NAO_USADO"}},
           "papeis": {"redator": "usado/m1"}}
    cliente_de_config(cfg)  # não pode levantar — provedor ocioso não exige chave
