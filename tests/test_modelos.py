"""Testes do roteamento multi-provider (ClienteRoteador, pronto) e
testes-CONTRATO do ClienteOpenAICompat (T5 — fabricação DeepSeek).

Os testes do contrato ficam em skip enquanto a classe não existe.
Quando o T5 implementar `ClienteOpenAICompat` em motor/modelos.py,
eles ativam sozinhos e são o DoD: NUNCA ajustar o teste à implementação.
"""
from __future__ import annotations

import types

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


# ---------------------------------------------------- roteamento por tier (Corte A)

def test_roteador_tier_resolve_e_emite_evento():
    simples, padrao = _stub("do-tier"), _stub("do-claude")
    log = FakeLog()
    r = ClienteRoteador(padrao=padrao, tiers={"simples": simples}, log=log)
    assert r.chamar("qualquer-papel", "p", tier="simples") == "do-tier"
    assert len(simples.chamadas) == 1
    assert "modelo.roteado_tier" in log.tipos()


def test_roteador_tier_fora_da_tabela_cai_no_papel():
    barato, padrao = _stub("do-barato"), _stub("do-claude")
    r = ClienteRoteador(padrao=padrao, mapa={"redator": barato}, tiers={"simples": _stub("x")})
    # tier desconhecido → ignora tiers, usa o mapa por papel
    assert r.chamar("redator", "p", tier="inexistente") == "do-barato"
    # sem tier → idem
    assert r.chamar("redator", "p") == "do-barato"


def test_roteador_tier_precede_papel():
    por_tier, por_papel, padrao = _stub("do-tier"), _stub("do-papel"), _stub("do-claude")
    r = ClienteRoteador(padrao=padrao, mapa={"redator": por_papel}, tiers={"complexa": por_tier})
    assert r.chamar("redator", "p", tier="complexa") == "do-tier"
    assert len(por_papel.chamadas) == 0


def test_roteador_tier_ferramentas_desvia_ao_padrao():
    por_tier, padrao = _stub("do-tier"), _stub("do-claude")
    por_tier.suporta_ferramentas = False
    log = FakeLog()
    r = ClienteRoteador(padrao=padrao, tiers={"simples": por_tier}, log=log)
    assert r.chamar("p", "x", ferramentas="WebSearch", tier="simples") == "do-claude"
    assert "modelo.roteado_ferramentas" in log.tipos()


def test_roteador_tier_none_faz_fallback_ao_padrao():
    por_tier, padrao = _stub(None), _stub("do-claude")
    log = FakeLog()
    r = ClienteRoteador(padrao=padrao, tiers={"simples": por_tier}, log=log)
    assert r.chamar("p", "x", tier="simples") == "do-claude"
    assert "modelo.fallback" in log.tipos()


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


# ----------------------------------------------------- ClienteCodex (executor)

def _proc(rc=0, out="", err=""):
    return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)


def _codex(monkeypatch, resultados, **kw):
    """ClienteCodex com subprocess.run mockado. `resultados` é lista de
    SimpleNamespace (rc/stdout/stderr) ou Exception (falha transiente).
    Devolve (cliente, cmds) onde cmds capta cada lista de comando enviada."""
    from motor.modelos import ClienteCodex
    kw.setdefault("backoff", 0)
    c = ClienteCodex(log=kw.pop("log", None), **kw)
    cmds: list[list[str]] = []
    fila = list(resultados)

    def fake_run(cmd, **_):
        cmds.append(cmd)
        r = fila.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(modelos.subprocess, "run", fake_run)
    return c, cmds


def test_codex_sucesso_devolve_stdout_limpo(monkeypatch):
    c, cmds = _codex(monkeypatch, [_proc(0, "  resultado  ")])
    assert c.chamar("pesquisador", "investigue X") == "resultado"
    cmd = cmds[0]
    assert cmd[:4] == ["codex", "exec", "--skip-git-repo-check", "--ephemeral"]
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"  # default seguro
    assert cmd[-1] == "investigue X"
    assert "-m" not in cmd and "--search" not in cmd  # default → sem -m, sem busca ao vivo


def test_codex_suporta_ferramentas_e_adiciona_search(monkeypatch):
    from motor.modelos import ClienteCodex
    assert ClienteCodex.suporta_ferramentas is True  # Codex é agêntico, atende ferramentas
    c, cmds = _codex(monkeypatch, [_proc(0, "ok")])
    assert c.chamar("pesquisador", "p", ferramentas="WebSearch") == "ok"
    assert "--search" in cmds[0]  # ferramenta pedida → busca ao vivo


def test_codex_sandbox_e_busca_configuraveis(monkeypatch):
    c, cmds = _codex(monkeypatch, [_proc(0, "ok")],
                     sandbox="workspace-write", busca_ao_vivo=True)
    c.chamar("pesquisador", "p")
    assert cmds[0][cmds[0].index("--sandbox") + 1] == "workspace-write"
    assert "--search" in cmds[0]  # busca_ao_vivo → --search mesmo sem ferramenta


def test_codex_modelo_por_papel_vira_flag_m(monkeypatch):
    c, cmds = _codex(monkeypatch, [_proc(0, "ok")],
                     mapa_papeis={"pesquisador": "gpt-5-codex"})
    c.chamar("pesquisador", "p")
    assert "-m" in cmds[0] and cmds[0][cmds[0].index("-m") + 1] == "gpt-5-codex"


def test_codex_retry_em_rc_nao_zero(monkeypatch):
    log = FakeLog()
    c, cmds = _codex(monkeypatch, [_proc(1, "", "throttle"), _proc(0, "ok")], log=log)
    assert c.chamar("pesquisador", "p") == "ok"
    assert len(cmds) == 2
    assert log.tipos().count("modelo.falha") == 1


def test_codex_falha_total_devolve_none(monkeypatch):
    log = FakeLog()
    c, cmds = _codex(monkeypatch, [_proc(1, ""), OSError("crash"), _proc(2, "")],
                     log=log, tentativas=3)
    assert c.chamar("pesquisador", "p") is None
    assert len(cmds) == 3
    assert log.tipos().count("modelo.falha") == 3


def test_codex_integra_com_roteador_executor_claude_julga(monkeypatch):
    c, _ = _codex(monkeypatch, [_proc(0, "do-codex"), _proc(0, "do-codex-search")])
    padrao = _stub("do-claude")
    r = ClienteRoteador(padrao=padrao, mapa={"pesquisador": c})
    # executor → codex
    assert r.chamar("pesquisador", "p") == "do-codex"
    # papel de julgamento → claude (padrão), nunca codex
    assert r.chamar("verifier", "p") == "do-claude"
    # ferramentas → Codex atende (suporta_ferramentas=True), NÃO desvia ao claude
    assert r.chamar("pesquisador", "p", ferramentas="WebSearch") == "do-codex-search"


def test_config_codex_executor_sem_chave(monkeypatch):
    from motor.modelos import ClienteCodex, cliente_de_config
    cfg = {"provedores": {"codex": {"tipo": "codex"}},
           "papeis": {"pesquisador": "codex/default", "analista-custos": "codex/default"}}
    r = cliente_de_config(cfg)  # não pode exigir chave de API
    assert set(r.mapa) == {"pesquisador", "analista-custos"}
    assert isinstance(r.mapa["pesquisador"], ClienteCodex)
    assert r.mapa["pesquisador"] is r.mapa["analista-custos"]  # mesmo provedor, mesmo cliente
    assert "verifier" not in r.mapa and "evaluator" not in r.mapa  # julgamento fica no claude


def test_config_provedor_tipo_desconhecido_falha(monkeypatch):
    from motor.modelos import cliente_de_config
    cfg = {"provedores": {"x": {"tipo": "marciano"}}, "papeis": {"redator": "x/m"}}
    with pytest.raises(ValueError):
        cliente_de_config(cfg)


# ------------------------------------------------- cliente_de_config: tiers (Corte A)

def test_config_tiers_codex_e_padrao(monkeypatch):
    from motor.modelos import ClienteCodex, ClienteClaudeCLI, cliente_de_config
    cfg = {"provedores": {"codex": {"tipo": "codex"}},
           "tiers": {"simples": "codex/default", "complexa": "padrao"}}
    r = cliente_de_config(cfg)  # só-tiers, sem 'papeis' → não pode quebrar
    assert set(r.tiers) == {"simples", "complexa"}
    assert isinstance(r.tiers["simples"], ClienteCodex)
    assert r.tiers["complexa"] is r.padrao  # "padrao" referencia o claude
    assert isinstance(r.padrao, ClienteClaudeCLI)
    assert r.mapa == {}  # sem papeis


def test_config_tiers_e_papeis_coexistem(monkeypatch):
    from motor.modelos import cliente_de_config
    cfg = {"provedores": {"codex": {"tipo": "codex"}},
           "tiers": {"media": "codex/default"},
           "papeis": {"pesquisador": "codex/default"}}
    r = cliente_de_config(cfg)
    assert set(r.tiers) == {"media"} and set(r.mapa) == {"pesquisador"}


def test_config_tier_destino_invalido_falha(monkeypatch):
    from motor.modelos import cliente_de_config
    cfg = {"provedores": {"codex": {"tipo": "codex"}},
           "tiers": {"media": "fantasma/modelo"}}  # provedor não declarado
    with pytest.raises(ValueError):
        cliente_de_config(cfg)


def test_config_tiers_openai_compat_exige_chave(monkeypatch):
    from motor.modelos import ClienteOpenAICompat, cliente_de_config
    monkeypatch.setenv("K_NV", "x")
    cfg = {"provedores": {"nvidia": {"base_url": "https://nv/v1", "api_key_env": "K_NV"}},
           "tiers": {"simples": "nvidia/deepseek-ai/deepseek-v4"}}
    r = cliente_de_config(cfg)
    assert isinstance(r.tiers["simples"], ClienteOpenAICompat)
    assert r.tiers["simples"].modelo == "deepseek-ai/deepseek-v4"
