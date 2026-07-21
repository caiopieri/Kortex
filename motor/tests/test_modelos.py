"""Testes do roteamento multi-provider (ClienteRoteador, pronto) e
testes-CONTRATO do ClienteOpenAICompat (T5 — fabricação DeepSeek).

Os testes do contrato ficam em skip enquanto a classe não existe.
Quando o T5 implementar `ClienteOpenAICompat` em motor/modelos.py,
eles ativam sozinhos e são o DoD: NUNCA ajustar o teste à implementação.
"""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from motor import modelos
from motor.modelos import ClienteRoteador, ClienteStub, extrai_json


# ---------------------------------------------------------------- extrai_json

@pytest.mark.parametrize("texto, esperado", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('```\n{"a": 1}\n```', {"a": 1}),
    ('Aqui está o JSON:\n{"a": 1}', {"a": 1}),
    ('{"a": 1}\nNota: use {x} com cuidado.', {"a": 1}),       # chave solta DEPOIS
    ('Veja o objeto { resultado }: {"a": 1}', {"a": 1}),       # chave solta ANTES
    ('{"a": {"b": 2}, "c": [1, 2]}', {"a": {"b": 2}, "c": [1, 2]}),
    ('{"t": "use {chaves} e } aqui"}', {"t": "use {chaves} e } aqui"}),  # chaves em string
    ('[1, 2, 3]', None),         # topo não-objeto
    ('nenhum json aqui', None),
    ('', None),
    ('{"a": ', None),            # quebrado
])
def test_extrai_json_robusto(texto, esperado):
    assert extrai_json(texto) == esperado


class FakeLog:
    def __init__(self):
        self.eventos: list[tuple[str, dict]] = []

    def evento(self, tipo: str, **dados):
        self.eventos.append((tipo, dados))

    def tipos(self) -> list[str]:
        return [t for t, _ in self.eventos]


# ---------------------------------------------------------------- roteador

def _stub(resposta, sempre_none: bool = False):
    return ClienteStub(lambda papel, prompt: resposta, sempre_none=sempre_none)


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


def test_roteador_auto_esgotar_percorre_cadeia_e_fica_sticky():
    a = _stub_prov(None, "A", sempre_none=True)
    b = _stub_prov(None, "B", sempre_none=True)
    c = _stub_prov("do-c", "C")
    padrao = _stub_prov("do-padrao", "padrao")
    log = FakeLog()
    r = ClienteRoteador(padrao=padrao, mapa={"redator": a}, cadeia=[a, b, c],
                        auto_esgotar=True, log=log)

    assert r.chamar("redator", "p") == "do-c"
    assert r.esgotados == {"A", "B"}
    assert log.tipos().count("provedor.auto_esgotado") == 2

    assert r.chamar("redator", "p2") == "do-c"
    assert len(a.chamadas) == 1
    assert len(b.chamadas) == 1
    assert len(c.chamadas) == 2


def test_roteador_auto_esgotar_tudo_falha_devolve_none_e_esgota_todos():
    a = _stub_prov(None, "A", sempre_none=True)
    b = _stub_prov(None, "B", sempre_none=True)
    padrao = _stub_prov(None, "P", sempre_none=True)
    r = ClienteRoteador(padrao=padrao, mapa={"redator": a}, cadeia=[a, b],
                        auto_esgotar=True)

    assert r.chamar("redator", "p") is None
    assert r.esgotados == {"A", "B", "P"}


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


# --------------------------------------- disponibilidade / esgotamento (Corte B)

def _stub_prov(resposta, provedor, sempre_none: bool = False):
    s = ClienteStub(lambda papel, prompt: resposta, sempre_none=sempre_none)
    s.provedor = provedor
    return s


def _stub_modelo(resposta, provedor, modelo, sempre_none: bool = False):
    s = _stub_prov(resposta, provedor, sempre_none=sempre_none)
    s.modelo = modelo
    return s


def test_roteador_descricao_de_resolve_modelo_concreto_sem_emitir_evento():
    simples = _stub_modelo("do-tier", "nv-llama", "meta/llama-3.3-70b-instruct")
    pin = _stub_modelo("do-pin", "nv-qwen", "qwen/qwen3-coder")
    padrao = _stub_modelo("do-claude", "claude", "sonnet")
    log = FakeLog()
    r = ClienteRoteador(
        padrao=padrao,
        tiers={"simples": simples},
        pins={"synthesizer": pin},
        log=log,
    )

    assert r.descricao_de("pesquisador", tier="simples") == "nv-llama/meta/llama-3.3-70b-instruct"
    assert r.descricao_de("synthesizer") == "nv-qwen/qwen/qwen3-coder"
    assert log.eventos == []


def test_roteador_descricao_de_usa_mapa_papeis_do_cliente_compartilhado():
    cliente = _stub_prov("ok", "nvidia")
    cliente.modelo = "modelo-default"
    cliente.mapa_papeis = {"redator": "deepseek-v4", "analista": "kimi-k2.6"}
    r = ClienteRoteador(padrao=_stub("padrao"), mapa={"redator": cliente, "analista": cliente})

    assert r.descricao_de("redator") == "nvidia/deepseek-v4"
    assert r.descricao_de("analista") == "nvidia/kimi-k2.6"


def test_esgotar_claude_reroteia_julgamento_ao_codex():
    """Synthesizer (papel sem tier → padrao=claude)
    com claude esgotado deve cair no Codex, não pendurar."""
    claude = _stub_prov("do-claude", "claude")
    codex = _stub_prov("do-codex", "codex")
    log = FakeLog()
    r = ClienteRoteador(padrao=claude, cadeia=[codex], esgotados={"claude"}, log=log)
    assert r.chamar("synthesizer", "feche a missão") == "do-codex"
    assert len(claude.chamadas) == 0  # nem tentou o claude esgotado
    assert "modelo.reroteado_esgotado" in log.tipos()


def test_esgotar_codex_executor_cai_no_claude():
    claude = _stub_prov("do-claude", "claude")
    codex = _stub_prov("do-codex", "codex")
    r = ClienteRoteador(padrao=claude, tiers={"simples": codex}, cadeia=[codex],
                        esgotados={"codex"})
    # tarefa simples iria pro codex, mas está esgotado → padrao (claude)
    assert r.chamar("pesquisador", "x", tier="simples") == "do-claude"


def test_sem_esgotados_nao_reroteia():
    claude = _stub_prov("do-claude", "claude")
    codex = _stub_prov("do-codex", "codex")
    r = ClienteRoteador(padrao=claude, tiers={"simples": codex}, cadeia=[codex])
    assert r.chamar("pesquisador", "x", tier="simples") == "do-codex"


def test_tudo_esgotado_nao_trava_devolve_original():
    claude = _stub_prov("do-claude", "claude")
    codex = _stub_prov("do-codex", "codex")
    r = ClienteRoteador(padrao=claude, cadeia=[codex], esgotados={"claude", "codex"})
    # nada disponível: devolve o original (deixa falhar/responder, não entra em loop)
    assert r.chamar("synthesizer", "x") == "do-claude"


# --------------------------------------------------------- construção de cliente

def test_construir_cliente_sem_config_e_sem_claude_levanta_erro_tipado(monkeypatch):
    from motor.__main__ import construir_cliente
    from motor.modelos import ProvedorIndisponivel

    monkeypatch.setattr(modelos.ClienteClaudeCLI, "disponivel", staticmethod(lambda: False))

    with pytest.raises(ProvedorIndisponivel):
        construir_cliente(None, None)


def test_construir_cliente_sem_config_com_claude_devolve_cliente_cli(monkeypatch):
    from motor.__main__ import construir_cliente
    from motor.modelos import ClienteClaudeCLI

    monkeypatch.setattr(modelos.ClienteClaudeCLI, "disponivel", staticmethod(lambda: True))

    assert isinstance(construir_cliente(None, None), ClienteClaudeCLI)


def test_main_sem_config_orcada_mantem_saida_humana(monkeypatch, capsys):
    from motor import __main__ as cli

    monkeypatch.setattr(cli.sys, "argv", ["python -m motor", "missao"])
    monkeypatch.setattr(modelos.ClienteClaudeCLI, "disponivel", staticmethod(lambda: False))

    assert cli.main() == 1
    saida = capsys.readouterr().out
    assert "erro: orçamento indisponível: configuracao orcada ausente" in saida


def test_config_esgotados_e_cadeia(monkeypatch):
    from motor.modelos import cliente_de_config
    cfg = {"provedores": {"codex": {"tipo": "codex"}},
           "tiers": {"simples": "codex/default", "complexa": "padrao"},
           "esgotados": ["claude"]}
    r = cliente_de_config(cfg)
    assert r.esgotados == {"claude"}
    # cadeia tem o cliente do codex (não-padrao) como fallback
    assert any(getattr(c, "provedor", None) == "codex" for c in r.cadeia)
    # claude esgotado → _disponivel reroteia o padrao pro codex (sem shell out)
    assert getattr(r._disponivel(r.padrao), "provedor", None) == "codex"


def test_config_auto_esgotar_ordenacao_por_custo():
    from motor.modelos import cliente_de_config
    cfg = {
        "auto_esgotar": True,
        "provedores": {
            "caro": {"tipo": "opencode", "custo_ordem": 30},
            "barato": {"tipo": "opencode", "custo_ordem": 1},
            "medio": {"tipo": "codex", "custo_ordem": 10},
        },
        "papeis": {"redator": "caro/openai/gpt-5.5"},
        "tiers": {"simples": "barato/openai/gpt-5.5", "media": "medio/default"},
    }
    r = cliente_de_config(cfg)
    assert r.auto_esgotar is True
    assert [getattr(c, "provedor", None) for c in r.cadeia] == ["barato", "codex", "caro"]


def test_registro_ordena_cadeia_por_custo(tmp_path):
    from motor.registro import cliente_de_registro

    for nome, provedor, custo in [
        ("alto.md", "alto", 30),
        ("baixo.md", "baixo", 1),
        ("medio.md", "medio", 10),
    ]:
        (tmp_path / nome).write_text(
            "---\n"
            "tipo: modelo-executor\n"
            "transporte: opencode\n"
            f"provedor: {provedor}\n"
            f"custo_ordem: {custo}\n"
            "---\n",
            encoding="utf-8",
        )

    r = cliente_de_registro(tmp_path)
    assert [getattr(c, "provedor", None) for c in r.cadeia] == ["baixo", "medio", "alto"]


# ------------------------------------------- contrato ClienteOpenAICompat (T5)

OpenAICompat = getattr(modelos, "ClienteOpenAICompat", None)
t5 = pytest.mark.skipif(OpenAICompat is None,
                        reason="T5 pendente — ClienteOpenAICompat ainda não fabricado")


def _resposta_ok(conteudo="olá"):
    return {"choices": [{"message": {"role": "assistant", "content": conteudo}}]}


def _resposta_ok_com_uso(conteudo="olá"):
    return {
        **_resposta_ok(conteudo),
        "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
    }


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
def test_compat_emite_modelo_uso_quando_resposta_tem_usage(monkeypatch):
    log = FakeLog()
    c, _ = _cliente(
        monkeypatch,
        [_resposta_ok_com_uso("ok")],
        log=log,
        provedor="nvidia",
        mapa_papeis={"redator": "moonshotai/kimi-k2.6"},
    )

    assert c.chamar("redator", "p") == "ok"

    dados_uso = {
        "papel": "redator",
        "provedor": "nvidia",
        "modelo": "moonshotai/kimi-k2.6",
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert log.eventos == [("modelo.uso", dados_uso), ("custo.tick", dados_uso)]


@t5
def test_compat_sem_usage_nao_emite_modelo_uso(monkeypatch):
    log = FakeLog()
    c, _ = _cliente(monkeypatch, [_resposta_ok("ok")], log=log)

    assert c.chamar("redator", "p") == "ok"
    assert "modelo.uso" not in log.tipos()


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


# ----------------------------------------------------- ClienteOpenCode (3º executor)

def _opencode(monkeypatch, resultados, **kw):
    from motor.modelos import ClienteOpenCode
    kw.setdefault("backoff", 0)
    c = ClienteOpenCode(log=kw.pop("log", None), **kw)
    cmds: list[list[str]] = []
    envs: list[dict] = []
    fila = list(resultados)

    def fake_run(cmd, **kwargs):
        cmds.append(cmd)
        envs.append(kwargs.get("env") or {})
        r = fila.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(modelos.subprocess, "run", fake_run)
    return c, cmds, envs


def test_opencode_run_e_modelo(monkeypatch):
    from motor.modelos import ClienteOpenCode
    assert ClienteOpenCode.suporta_ferramentas is True
    c, cmds, _ = _opencode(monkeypatch, [_proc(0, "  saída  ")],
                           mapa_papeis={"redator": "openai/gpt-5.5"})
    assert c.chamar("redator", "escreva X") == "saída"
    cmd = cmds[0]
    assert cmd[:2] == ["opencode", "run"]
    assert cmd[cmd.index("-m") + 1] == "openai/gpt-5.5"
    assert cmd[-1] == "escreva X"


def test_opencode_permissao_vira_env(monkeypatch):
    c, cmds, envs = _opencode(monkeypatch, [_proc(0, "ok")],
                              permissao='{"edit":"deny"}')
    c.chamar("redator", "p")
    assert envs[0].get("OPENCODE_PERMISSION") == '{"edit":"deny"}'


def test_opencode_retry_e_provedor(monkeypatch):
    log = FakeLog()
    c, cmds, _ = _opencode(monkeypatch, [_proc(1, "", "boom"), _proc(0, "ok")],
                           log=log, provedor="oc")
    assert c.chamar("redator", "p") == "ok"
    assert len(cmds) == 2 and log.tipos().count("modelo.falha") == 1
    assert c.provedor == "oc"


def test_config_tipo_opencode(monkeypatch):
    from motor.modelos import ClienteOpenCode, cliente_de_config
    cfg = {"provedores": {"oc": {"tipo": "opencode", "permissao": "{}"}},
           "papeis": {"redator": "oc/openai/gpt-5.5"}}
    r = cliente_de_config(cfg)
    assert isinstance(r.mapa["redator"], ClienteOpenCode)
    assert r.mapa["redator"].provedor == "oc"


# --------------------------------------------------------- pins manuais (controle)

def test_pin_por_papel_vence_tier_e_mapa():
    pin, por_tier, por_papel, padrao = (_stub("PIN"), _stub("TIER"),
                                        _stub("PAPEL"), _stub("CLAUDE"))
    log = FakeLog()
    r = ClienteRoteador(padrao=padrao, mapa={"redator": por_papel},
                        tiers={"simples": por_tier}, pins={"redator": pin}, log=log)
    assert r.chamar("redator", "p", tier="simples") == "PIN"
    assert "modelo.pin" in log.tipos()
    assert len(por_tier.chamadas) == 0 and len(por_papel.chamadas) == 0


def test_pin_curinga_vale_pra_tudo():
    pin, padrao = _stub("PIN"), _stub("CLAUDE")
    r = ClienteRoteador(padrao=padrao, pins={"*": pin})
    assert r.chamar("synthesizer", "x") == "PIN"   # "esse no todo"
    assert r.chamar("pesquisador", "y", tier="media") == "PIN"


def test_pin_por_tier():
    pin, padrao = _stub("PIN"), _stub("CLAUDE")
    r = ClienteRoteador(padrao=padrao, pins={"complexa": pin})
    assert r.chamar("modelador", "x", tier="complexa") == "PIN"
    assert r.chamar("modelador", "x", tier="simples") == "CLAUDE"  # outro tier não casa


def test_precedencia_pin_papel_sobre_pin_curinga():
    especifico, curinga, padrao = _stub("ESPECIFICO"), _stub("CURINGA"), _stub("CLAUDE")
    r = ClienteRoteador(padrao=padrao, pins={"verifier": especifico, "*": curinga})
    assert r.chamar("verifier", "x") == "ESPECIFICO"   # papel > "*"
    assert r.chamar("planner", "x") == "CURINGA"


def test_config_pins(monkeypatch):
    from motor.modelos import ClienteOpenCode, cliente_de_config
    cfg = {"provedores": {"oc": {"tipo": "opencode"}},
           "pins": {"synthesizer": "oc/openai/gpt-5.5"}}
    r = cliente_de_config(cfg)
    assert set(r.pins) == {"synthesizer"}
    assert isinstance(r.pins["synthesizer"], ClienteOpenCode)
    assert r.pins["synthesizer"].modelo == "openai/gpt-5.5"


# ------------------------------------ guard de independência do juiz (cross-model)

def test_provedor_de_preve_roteamento():
    codex, claude = _stub_prov("c", "codex"), _stub_prov("k", "claude")
    r = ClienteRoteador(padrao=claude, tiers={"media": codex})
    assert r.provedor_de("pesquisador", tier="media") == "codex"
    assert r.provedor_de("verifier") == "claude"   # julgamento → padrão


def test_juiz_evita_provedor_do_executor():
    """Verifier não pode cair no mesmo provedor do executor que julga."""
    codex, claude = _stub_prov("do-codex", "codex"), _stub_prov("do-claude", "claude")
    log = FakeLog()
    # verifier resolveria pro codex (via pin de tier), mas o executor é codex → desvia
    r = ClienteRoteador(padrao=claude, tiers={"media": codex}, cadeia=[codex], log=log)
    # simula: verifier roteado ao codex, mas evitar=codex (provedor do executor)
    assert r.chamar("verifier", "x", tier="media", evitar="codex") == "do-claude"
    assert "juiz.independencia" in log.tipos()


def test_juiz_sem_conflito_nao_desvia():
    codex, claude = _stub_prov("do-codex", "codex"), _stub_prov("do-claude", "claude")
    r = ClienteRoteador(padrao=claude, tiers={"media": codex})
    # verifier no claude, executor no codex → sem conflito, não desvia
    assert r.chamar("verifier", "x", evitar="codex") == "do-claude"


def test_pin_vence_guard_do_juiz():
    """Pin explícito do operador no verifier vence o guard."""
    codex_pin, claude = _stub_prov("PIN-CODEX", "codex"), _stub_prov("do-claude", "claude")
    r = ClienteRoteador(padrao=claude, pins={"verifier": codex_pin}, cadeia=[claude])
    # mesmo com evitar=codex, o pin manda
    assert r.chamar("verifier", "x", evitar="codex") == "PIN-CODEX"


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


def test_config_codex_resolve_papeis_do_planner_por_tier_e_capacidade(monkeypatch):
    from motor.modelos import cliente_de_config

    cfg = json.loads(
        (Path(__file__).parent.parent / "exemplos" / "modelos-codex.json").read_text()
    )
    roteador = cliente_de_config(cfg)
    monkeypatch.setattr(
        roteador.tiers["media"], "chamar", lambda *_args, **_kwargs: "CODEX"
    )
    monkeypatch.setattr(
        roteador.padrao, "chamar", lambda *_args, **_kwargs: "CLAUDE"
    )

    assert roteador.descricao_de(
        "redator", tier="media", capacidades=["redacao"]
    ) == "codex/default"
    assert roteador.chamar(
        "redator", "p", tier="media", capacidades=["redacao"]
    ) == "CODEX"
    assert roteador.descricao_de(
        "analista", tier="complexa", capacidades=["calculo", "raciocinio-longo"]
    ) == "claude"
    assert roteador.chamar(
        "analista", "p", tier="complexa",
        capacidades=["calculo", "raciocinio-longo"],
    ) == "CLAUDE"


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
