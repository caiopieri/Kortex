import json
import sys
from decimal import Decimal

import pytest

from motor.__main__ import _drenar_orcamento_cli, main
from motor.composicao_orcamento import (
    PRICING_CAPTURADO_EM, PRICING_MAX_AGE_S, ClienteSomenteOrcado,
    RotaOrcadaCertificada, compor_orcamento_openai, validar_independencia_orcada,
)
from motor.modelos import ClienteOpenAICompat, ClienteStub
from motor.eventos import LogEventos
from motor.openai_orcado import PRICING_VERSION
from motor.orcamento import (
    ErroOrcamento, IdentidadeTentativaCusteada, RequisitosTentativaCusteada,
    ReservaOrcamento, RepositorioOrcamento, executar_tentativa_custeada,
    publicar_um_pendente,
)
from tests.helpers_grafo import composicao_stub


def _cfg(capturado_em=PRICING_CAPTURADO_EM):
    return {"orcamento_openai": {
        "api_key_env": "OPENAI_API_KEY",
        "capacidades": ["pesquisa", "redacao"],
        "max_completion_tokens": 100,
        "fx": {"versao": "ptax-2026-07-14", "capturado_em": capturado_em,
               "cotacao_venda": "5.50"},
        "fx_max_age_s": 3600,
        "margem": "1.20",
        "teto_bootstrap_brl": "25.00",
        "timeout": 30,
    }}


def _rota(route_id: str, provider_id: str, *papeis: str) -> RotaOrcadaCertificada:
    return RotaOrcadaCertificada(route_id, provider_id, frozenset(papeis))


def test_preflight_aceita_executor_e_verifier_em_providers_distintos():
    validar_independencia_orcada((
        _rota("rota-executor", "provider-a", "executor"),
        _rota("rota-verifier", "provider-b", "verifier"),
    ))


@pytest.mark.parametrize("rotas", [
    (),
    [],
    (_rota("rota", "provider-a", "executor", "verifier"),),
    (
        _rota("rota-a", "provider-a", "executor"),
        _rota("rota-b", "provider-a", "verifier"),
    ),
    (_rota("rota-a", "provider-a", "executor"),),
    (_rota("rota-b", "provider-b", "verifier"),),
])
def test_preflight_rejeita_catalogo_sem_independencia(rotas):
    with pytest.raises(ErroOrcamento):
        validar_independencia_orcada(rotas)


@pytest.mark.parametrize("rotas", [
    (object(),),
    (_rota("", "provider-a", "executor"),),
    (_rota("ROTA", "provider-a", "executor"),),
    (_rota("rota/alias", "provider-a", "executor"),),
    (_rota("a" * 129, "provider-a", "executor"),),
    (_rota("rota", "", "executor"),),
    (_rota("rota", "Provider", "executor"),),
    (_rota("rota", "provider:alias", "executor"),),
    (_rota("rota", "a" * 65, "executor"),),
    (RotaOrcadaCertificada("rota", "provider-a", set(["executor"])),),
    (_rota("rota", "provider-a"),),
    (_rota("rota", "provider-a", "planner"),),
    (
        _rota("duplicada", "provider-a", "executor"),
        _rota("duplicada", "provider-b", "verifier"),
    ),
])
def test_preflight_rejeita_topologia_hostil(rotas):
    with pytest.raises(ErroOrcamento):
        validar_independencia_orcada(rotas)


def test_composicao_stub_emite_as_identidades_certificadas(tmp_path):
    deps = composicao_stub(ClienteStub(lambda *_args: "ok"), tmp_path / "stub")
    executor = deps.fabrica(
        "pesquisador", "p", 1, RequisitosTentativaCusteada(),
    )[0]
    verifier = deps.fabrica(
        "verifier", "p", 1,
        RequisitosTentativaCusteada(evitar_provedor=executor.provider_id),
    )[0]

    assert (executor.route_id, executor.provider_id) == (
        "stub:executor", "stub-provider-executor",
    )
    assert (verifier.route_id, verifier.provider_id) == (
        "stub:verifier", "stub-provider-verifier",
    )
    assert {executor.route_id, verifier.route_id} == {
        rota.route_id for rota in deps.rotas_certificadas
    }


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
    assert deps.teto_bootstrap == Decimal("25.00")


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


@pytest.mark.parametrize("mutacao", [
    "ausente", "extra", "decimal_float", "teto_ausente", "teto_float", "env_vazia",
])
def test_config_hostil_falha_fechado(tmp_path, monkeypatch, mutacao):
    monkeypatch.setenv("OPENAI_API_KEY", "segredo")
    cfg = _cfg()
    if mutacao == "ausente":
        cfg = {}
    elif mutacao == "extra":
        cfg["orcamento_openai"]["surpresa"] = True
    elif mutacao == "decimal_float":
        cfg["orcamento_openai"]["margem"] = 1.2
    elif mutacao == "teto_ausente":
        del cfg["orcamento_openai"]["teto_bootstrap_brl"]
    elif mutacao == "teto_float":
        cfg["orcamento_openai"]["teto_bootstrap_brl"] = 25.0
    else:
        monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ErroOrcamento):
        compor_orcamento_openai(cfg, tmp_path, relogio=lambda: PRICING_CAPTURADO_EM)


def test_cli_injeta_identidade_repositorio_e_fabrica(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "segredo")
    cfg = tmp_path / "modelos.json"
    cfg.write_text(json.dumps(_cfg()), encoding="utf-8")
    observado = {}
    drains = []

    class Grafo:
        def invoke(self, entrada, config):
            observado.update(entrada=entrada, config=config)
            return {"avaliacao": {"abortada": True}}

    def construir(cliente, _log, **kwargs):
        observado.update(cliente=cliente, kwargs=kwargs)
        return Grafo()

    cliente = ClienteStub(lambda *_args: "ok")
    monkeypatch.setattr(
        "motor.__main__.compor_orcamento_openai",
        lambda *_args, **_kwargs: composicao_stub(cliente, tmp_path / "orcamento-cli"),
    )
    monkeypatch.setattr("motor.__main__.construir_grafo", construir)
    monkeypatch.setattr(
        "motor.__main__._drenar_orcamento_cli",
        lambda _repo, run_id, _log: drains.append(run_id) or True,
    )
    monkeypatch.setattr(sys, "argv", [
        "motor", "missao", "--modelos", str(cfg), "--workspace", str(tmp_path),
        "--run-id", "run-config-1",
    ])

    assert main() == 0
    assert observado["cliente"] is cliente
    assert observado["entrada"]["run_id"] == observado["entrada"]["thread_id"] == "run-config-1"
    assert observado["config"]["configurable"]["thread_id"] == "run-config-1"
    assert observado["kwargs"]["repositorio_orcamento"] is not None
    assert callable(observado["kwargs"]["fabrica_tentativas_orcadas"])
    assert drains == ["run-config-1", "run-config-1"]


def test_cli_redelivera_outbox_apos_lease_sem_ack(tmp_path):
    repo = RepositorioOrcamento(tmp_path / "orcamento")
    sessao = repo.sessao("run", "run", Decimal("10"))
    reserva = ReservaOrcamento("reserva", "call", "rota", 1, Decimal("1"), "v1")
    assert repo.reservar_exclusiva(sessao, reserva).status == "NOVA"

    def falhar(*_args):
        raise RuntimeError("sink indisponível")

    with pytest.raises(RuntimeError, match="sink indisponível"):
        publicar_um_pendente(repo, "run", "cli-antiga", 10, 5, falhar)

    log = LogEventos(tmp_path / "eventos.jsonl")
    try:
        assert not _drenar_orcamento_cli(repo, "run", log, agora=14)
        assert _drenar_orcamento_cli(repo, "run", log, agora=15)
    finally:
        log.fechar()
    assert repo.listar_pendentes("run") == []


@pytest.mark.parametrize("argv", [
    ["motor", "missao", "--run-id"],
    ["motor", "missao", "--run-id", "a..b"],
    ["motor", "missao", "--caixa", "caixa"],
])
def test_cli_rejeita_identidade_ausente_ou_invalida(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    assert main() == 2


def test_cli_caixa_injeta_mesma_identidade_e_dependencias(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "segredo")
    cfg = tmp_path / "modelos.json"
    cfg.write_text(json.dumps(_cfg()), encoding="utf-8")
    observado = {}

    class Conn:
        def close(self):
            observado["fechou"] = True

    class Saver:
        def __init__(self, _conn):
            pass

        def setup(self):
            pass

    monkeypatch.setattr("motor.__main__.sqlite3.connect", lambda *_args, **_kwargs: Conn())
    monkeypatch.setattr("motor.__main__.SqliteSaver", Saver)
    monkeypatch.setattr("motor.__main__.CaixaFundador", lambda *_args: object())
    monkeypatch.setattr("motor.__main__._drenar_orcamento_cli", lambda *_args: True)
    cliente = ClienteStub(lambda *_args: "ok")
    monkeypatch.setattr(
        "motor.__main__.compor_orcamento_openai",
        lambda *_args, **_kwargs: composicao_stub(cliente, tmp_path / "orcamento-caixa"),
    )
    monkeypatch.setattr("motor.__main__.construir_grafo", lambda cliente, _log, **kwargs: (
        observado.update(cliente=cliente, kwargs=kwargs) or object()
    ))
    monkeypatch.setattr("motor.__main__.rodar_com_caixa", lambda _g, entrada, config, *_args: (
        observado.update(entrada=entrada, config=config) or {"avaliacao": {"abortada": True}}
    ))
    monkeypatch.setattr(sys, "argv", [
        "motor", "missao", "--modelos", str(cfg), "--workspace", str(tmp_path),
        "--caixa", str(tmp_path / "caixa"), "--run-id", "run-caixa-1",
    ])

    assert main() == 0
    assert observado["entrada"]["run_id"] == "run-caixa-1"
    assert observado["config"]["configurable"]["thread_id"] == "run-caixa-1"
    assert observado["kwargs"]["repositorio_orcamento"] is not None
    assert callable(observado["kwargs"]["fabrica_tentativas_orcadas"])
    assert observado["fechou"] is True


def test_cli_single_provider_falha_antes_de_relay_ou_grafo(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "segredo")
    cfg = tmp_path / "modelos.json"
    cfg.write_text(json.dumps(_cfg()), encoding="utf-8")
    efeitos: list[str] = []
    monkeypatch.setattr(
        "motor.__main__._drenar_orcamento_cli",
        lambda *_args: efeitos.append("relay") or True,
    )
    monkeypatch.setattr(
        "motor.__main__.construir_grafo",
        lambda *_args, **_kwargs: efeitos.append("grafo"),
    )
    monkeypatch.setattr(sys, "argv", [
        "motor", "missao", "--modelos", str(cfg), "--workspace", str(tmp_path),
        "--run-id", "run-single-provider",
    ])

    assert main() == 1
    assert efeitos == []
