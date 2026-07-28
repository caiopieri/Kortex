"""Composição operacional fail-closed do único adapter financeiro certificado."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable

from . import anthropic_orcado, gemini_orcado, openai_orcado
from .anthropic_orcado import ClienteAnthropicCusteado
from .gemini_orcado import ClienteGeminiCusteado
from .openai_orcado import (
    MAX_INPUT_TOKENS,
    MODELO,
    PRICING_SOURCE,
    PRICING_VERSION,
    ClienteOpenAICusteado,
    SnapshotFX,
    SnapshotPricing,
    TransporteHTTP,
)
from .orcamento import (
    ErroOrcamento,
    RequisitosTentativaCusteada,
    RepositorioOrcamento,
    RotaTentativaCusteada,
)

# 2026-07-28T00:00:00Z. Tabelas de gemini_orcado/anthropic_orcado/openai_orcado
# reconferidas nesta data contra os PRICING_SOURCE de cada uma.
# ESTE VALOR EXPIRA EM 7 DIAS (PRICING_MAX_AGE_S). Vencido, o motor recusa
# arrancar -- por desenho: preco velho e contencao monetaria velha. Renovar
# exige RECONFERIR os precos, nao so mexer no numero.
PRICING_CAPTURADO_EM = 1_785_196_800
PRICING_MAX_AGE_S = 7 * 24 * 60 * 60
FX_MAX_AGE_LIMITE_S = 24 * 60 * 60


class ClienteSomenteOrcado:
    """Metadados de rota; qualquer chamada fora do ledger é proibida."""

    provedor = "openai"
    modelo = MODELO
    suporta_ferramentas = False
    roteamento_capacidades_runtime = True

    def chamar(self, *_args, **_kwargs):
        raise ErroOrcamento("caminho de modelo nao orcado proibido")


@dataclass(frozen=True)
class RotaOrcadaCertificada:
    """Identidade code-owned de uma rota apta a papéis do grafo."""

    route_id: str
    provider_id: str
    papeis: frozenset[str]


@dataclass(frozen=True)
class DependenciasOrcamento:
    cliente: ClienteSomenteOrcado
    repositorio: RepositorioOrcamento
    fabrica: Callable[
        [str, str, int, RequisitosTentativaCusteada], list[RotaTentativaCusteada]
    ]
    rotas_certificadas: tuple[RotaOrcadaCertificada, ...]
    teto_bootstrap: Decimal


def validar_independencia_orcada(
    rotas: object,
) -> None:
    """Exige providers distintos e certificados para executor e verifier."""
    if type(rotas) is not tuple or not rotas:
        raise ErroOrcamento("catalogo de rotas certificadas ausente")
    route_ids: set[str] = set()
    por_papel: dict[str, set[str]] = {"executor": set(), "verifier": set()}
    for rota in rotas:
        if not isinstance(rota, RotaOrcadaCertificada):
            raise ErroOrcamento("rota certificada invalida")
        if (
            not isinstance(rota.route_id, str)
            or re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,127}", rota.route_id) is None
            or rota.route_id in route_ids
        ):
            raise ErroOrcamento("route_id certificado invalido ou duplicado")
        if (
            not isinstance(rota.provider_id, str)
            or re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", rota.provider_id) is None
        ):
            raise ErroOrcamento("provider_id certificado invalido")
        if (
            type(rota.papeis) is not frozenset
            or not rota.papeis
            or any(papel not in por_papel for papel in rota.papeis)
        ):
            raise ErroOrcamento("papeis certificados invalidos")
        route_ids.add(rota.route_id)
        for papel in rota.papeis:
            por_papel[papel].add(rota.provider_id)
    if not any(
        executor != verifier
        for executor in por_papel["executor"]
        for verifier in por_papel["verifier"]
    ):
        raise ErroOrcamento(
            "independencia executor-verifier exige dois providers certificados"
        )


def _inteiro(dados: dict, nome: str, *, maximo: int | None = None) -> int:
    valor = dados.get(nome)
    if type(valor) is not int or valor <= 0 or (maximo is not None and valor > maximo):
        raise ErroOrcamento(f"{nome} invalido")
    return valor


def _texto(dados: dict, nome: str) -> str:
    valor = dados.get(nome)
    if (not isinstance(valor, str) or not valor or valor != valor.strip()
            or len(valor) > 128 or any(ord(char) < 32 for char in valor)):
        raise ErroOrcamento(f"{nome} invalido")
    return valor


def _decimal(dados: dict, nome: str) -> Decimal:
    bruto = dados.get(nome)
    if (not isinstance(bruto, str) or len(bruto) > 16
            or re.fullmatch(r"(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,6})?", bruto) is None):
        raise ErroOrcamento(f"{nome} invalido")
    try:
        valor = Decimal(bruto)
    except Exception as erro:
        raise ErroOrcamento(f"{nome} invalido") from erro
    if not valor.is_finite() or valor <= 0:
        raise ErroOrcamento(f"{nome} invalido")
    return valor


def compor_orcamento_openai(
    cfg: dict, workspace: str | Path, *,
    relogio: Callable[[], int] = lambda: int(time.time()),
    transporte: TransporteHTTP | None = None,
) -> DependenciasOrcamento:
    bloco = cfg.get("orcamento_openai") if isinstance(cfg, dict) else None
    esperados = {
        "api_key_env", "capacidades", "max_completion_tokens", "fx", "fx_max_age_s",
        "margem", "teto_bootstrap_brl", "timeout",
    }
    if not isinstance(bloco, dict) or set(bloco) != esperados:
        raise ErroOrcamento("configuracao orcada ausente ou invalida")
    env = _texto(bloco, "api_key_env")
    if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", env) is None or not os.environ.get(env):
        raise ErroOrcamento("credencial OpenAI ausente")
    fx = bloco["fx"]
    if not isinstance(fx, dict) or set(fx) != {"versao", "capturado_em", "cotacao_venda"}:
        raise ErroOrcamento("snapshot FX invalido")
    snapshot_fx = SnapshotFX(
        _texto(fx, "versao"), _inteiro(fx, "capturado_em"), _decimal(fx, "cotacao_venda"),
    )
    completion = _inteiro(bloco, "max_completion_tokens")
    fx_max_age = _inteiro(bloco, "fx_max_age_s", maximo=FX_MAX_AGE_LIMITE_S)
    timeout = _inteiro(bloco, "timeout", maximo=600)
    margem = _decimal(bloco, "margem")
    teto_bootstrap = _decimal(bloco, "teto_bootstrap_brl")
    capacidades_brutas = bloco["capacidades"]
    if (not isinstance(capacidades_brutas, list) or not capacidades_brutas
            or any(not isinstance(item, str) for item in capacidades_brutas)):
        raise ErroOrcamento("capacidades invalidas")
    capacidades = frozenset(_texto({"item": item}, "item") for item in capacidades_brutas)
    if len(capacidades) != len(capacidades_brutas):
        raise ErroOrcamento("capacidades duplicadas")
    pricing = SnapshotPricing(PRICING_VERSION, PRICING_CAPTURADO_EM, PRICING_SOURCE)

    def fabricar(
        _papel: str, prompt: str, _tentativa: int, requisitos: RequisitosTentativaCusteada,
    ) -> list[RotaTentativaCusteada]:
        if (requisitos.evitar_provedor == "openai" or requisitos.ferramentas is not None
                or not set(requisitos.capacidades or ()) <= capacidades):
            return []
        agora = relogio()
        api_key = os.environ.get(env)
        if not api_key:
            raise ErroOrcamento("credencial OpenAI ausente")
        kwargs = {} if transporte is None else {"transporte": transporte}
        adaptador = ClienteOpenAICusteado(
            api_key=api_key, prompt=prompt, max_input_tokens=MAX_INPUT_TOKENS,
            max_completion_tokens=completion, fx=snapshot_fx, pricing=pricing,
            agora=agora, fx_max_age_s=fx_max_age, pricing_max_age_s=PRICING_MAX_AGE_S,
            margem=margem, timeout=timeout, **kwargs,
        )
        return [RotaTentativaCusteada("openai:gpt-5", "openai", adaptador)]

    return DependenciasOrcamento(
        ClienteSomenteOrcado(), RepositorioOrcamento(Path(workspace) / "orcamento"), fabricar,
        (RotaOrcadaCertificada(
            "openai:gpt-5", "openai", frozenset({"executor", "verifier"}),
        ),),
        teto_bootstrap,
    )


# --------------------------------------------------------------------------
# Composicao multi-provedor: a unica que satisfaz `validar_independencia_orcada`
# --------------------------------------------------------------------------
#
# `compor_orcamento_openai` devolve UMA rota certificada, com `openai` cobrindo
# executor E verifier -- ou seja, nunca passa na propria validacao de
# independencia. Nao e bug dela: e o contrato dizendo que produzir e julgar com
# o mesmo provedor nao vale. Producao precisa de dois provedores de verdade.
#
# Papeis (decisao do fundador):
#   planner    -> Anthropic  (planeja a ideia inteira)
#   executor   -> Gemini por padrao; OpenAI quando o roteamento pede alta
#                 complexidade (tier) e o Gemini nao serve
#   verifier   -> OpenAI quando o Gemini produziu; Anthropic quando a OpenAI
#                 produziu -- a preferencia e ORDENADA e o motor passa
#                 `evitar_provedor`, entao produtor != juiz vale nos DOIS
#                 caminhos, nao so no caso facil
#   evaluator  -> Anthropic  (revisa e aprova ou nao)
#   synthesizer-> OpenAI

_ESPERADOS_MULTI = {
    "gemini", "openai", "anthropic", "fx", "fx_max_age_s", "margem",
    "teto_bootstrap_brl", "timeout",
}
_ESPERADOS_PROVEDOR = {"api_key_env", "capacidades", "max_completion_tokens"}

# Preferencia ORDENADA por papel. A fabrica devolve a primeira rota elegivel;
# `evitar_provedor` derruba a preferida e a seguinte assume. E por isso que
# `verifier` lista openai antes de anthropic: no caminho normal (Gemini executa)
# quem julga e a OpenAI; quando a OpenAI executou, ela e evitada e sobra a
# Anthropic.
_PREFERENCIA_POR_PAPEL: dict[str, tuple[str, ...]] = {
    "planner": ("anthropic",),
    "executor": ("gemini", "openai"),
    "verifier": ("openai", "anthropic"),
    "evaluator": ("anthropic",),
    "synthesizer": ("openai",),
}


class _ClienteMultiSomenteOrcado(ClienteSomenteOrcado):
    """Metadados de rota do arranjo multi-provedor. Nenhuma chamada direta."""

    provedor = "multi"
    modelo = "gemini+openai+anthropic"


def _bloco_provedor(cfg: dict, nome: str) -> tuple[str, frozenset[str], int]:
    bloco = cfg.get(nome)
    if not isinstance(bloco, dict) or set(bloco) != _ESPERADOS_PROVEDOR:
        raise ErroOrcamento(f"bloco {nome} ausente ou invalido")
    env = _texto(bloco, "api_key_env")
    if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", env) is None or not os.environ.get(env):
        raise ErroOrcamento(f"credencial {nome} ausente")
    brutas = bloco["capacidades"]
    if (not isinstance(brutas, list) or not brutas
            or any(not isinstance(item, str) for item in brutas)):
        raise ErroOrcamento(f"capacidades {nome} invalidas")
    capacidades = frozenset(_texto({"item": item}, "item") for item in brutas)
    if len(capacidades) != len(brutas):
        raise ErroOrcamento(f"capacidades {nome} duplicadas")
    return env, capacidades, _inteiro(bloco, "max_completion_tokens")


def compor_orcamento_multi(
    cfg: dict, workspace: str | Path, *,
    relogio: Callable[[], int] = lambda: int(time.time()),
    transporte: TransporteHTTP | None = None,
) -> DependenciasOrcamento:
    """Compoe as tres rotas custeadas e devolve as duas certificadas.

    `evaluator` NAO entra em `rotas_certificadas` porque o catalogo certificado
    so admite os papeis que a independencia executor-verifier governa; a rota da
    Anthropic e roteavel pela fabrica sem ser certificada.
    """
    bloco = cfg if isinstance(cfg, dict) else None
    if not isinstance(bloco, dict) or not _ESPERADOS_MULTI <= set(bloco):
        raise ErroOrcamento("configuracao orcada ausente ou invalida")

    fx_bruto = bloco["fx"]
    if not isinstance(fx_bruto, dict) or set(fx_bruto) != {
        "versao", "capturado_em", "cotacao_venda"
    }:
        raise ErroOrcamento("snapshot FX invalido")
    fx_versao = _texto(fx_bruto, "versao")
    fx_capturado = _inteiro(fx_bruto, "capturado_em")
    fx_cotacao = _decimal(fx_bruto, "cotacao_venda")

    fx_max_age = _inteiro(bloco, "fx_max_age_s", maximo=FX_MAX_AGE_LIMITE_S)
    timeout = _inteiro(bloco, "timeout", maximo=600)
    margem = _decimal(bloco, "margem")
    teto_bootstrap = _decimal(bloco, "teto_bootstrap_brl")

    env_g, cap_g, tokens_g = _bloco_provedor(bloco, "gemini")
    env_o, cap_o, tokens_o = _bloco_provedor(bloco, "openai")
    env_a, cap_a, tokens_a = _bloco_provedor(bloco, "anthropic")

    kwargs = {} if transporte is None else {"transporte": transporte}

    def fabricar(
        papel: str, prompt: str, _tentativa: int, requisitos: RequisitosTentativaCusteada,
    ) -> list[RotaTentativaCusteada]:
        if requisitos.ferramentas is not None:
            return []
        agora = relogio()
        pedidas = set(requisitos.capacidades or ())

        catalogo = {
            "gemini": ("google", "google:gemini-2.5-pro", env_g, cap_g, tokens_g,
                       ClienteGeminiCusteado, gemini_orcado),
            "openai": ("openai", "openai:gpt-5", env_o, cap_o, tokens_o,
                       ClienteOpenAICusteado, openai_orcado),
            "anthropic": ("anthropic", "anthropic:sonnet-4-5", env_a, cap_a, tokens_a,
                          ClienteAnthropicCusteado, anthropic_orcado),
        }

        for nome in _PREFERENCIA_POR_PAPEL.get(papel, ()):
            provider_id, route_id, env, capacidades, tokens, classe, mod = catalogo[nome]
            if requisitos.evitar_provedor == provider_id or not pedidas <= capacidades:
                continue
            api_key = os.environ.get(env)
            if not api_key:
                raise ErroOrcamento(f"credencial {nome} ausente")
            adaptador = classe(
                api_key=api_key, prompt=prompt, max_input_tokens=mod.MAX_INPUT_TOKENS,
                max_completion_tokens=tokens,
                fx=mod.SnapshotFX(fx_versao, fx_capturado, fx_cotacao),
                pricing=mod.SnapshotPricing(
                    mod.PRICING_VERSION, PRICING_CAPTURADO_EM, mod.PRICING_SOURCE
                ),
                agora=agora, fx_max_age_s=fx_max_age,
                pricing_max_age_s=PRICING_MAX_AGE_S, margem=margem,
                timeout=timeout, **kwargs,
            )
            return [RotaTentativaCusteada(route_id, provider_id, adaptador)]
        return []

    return DependenciasOrcamento(
        _ClienteMultiSomenteOrcado(),
        RepositorioOrcamento(Path(workspace) / "orcamento"),
        fabricar,
        (
            # Catalogo certificado: so os papeis que a independencia governa.
            # `openai` aparece nos dois lados de proposito -- ela executa em alta
            # complexidade e julga no caminho normal. A validacao exige que
            # EXISTA um par com providers distintos (google x openai), e o
            # `evitar_provedor` garante em runtime que ela nunca julga a si mesma.
            RotaOrcadaCertificada("google:gemini-2.5-pro", "google", frozenset({"executor"})),
            RotaOrcadaCertificada("openai:gpt-5", "openai", frozenset({"executor", "verifier"})),
            RotaOrcadaCertificada("anthropic:sonnet-4-5", "anthropic", frozenset({"verifier"})),
        ),
        teto_bootstrap,
    )
