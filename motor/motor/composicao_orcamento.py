"""Composição operacional fail-closed do único adapter financeiro certificado."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from . import anthropic_orcado, gemini_orcado, omniroute_orcado, openai_orcado
from .anthropic_orcado import ClienteAnthropicCusteado
from .gemini_orcado import ClienteGeminiCusteado
from .omniroute_orcado import ClienteOmniRouteCusteado
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
    Moeda,
    RequisitosTentativaCusteada,
    RepositorioOrcamento,
    RotaTentativaCusteada,
)

# 2026-08-10T00:00:00Z. Tabelas de gemini_orcado/anthropic_orcado/openai_orcado
# e PRECOS de omniroute_orcado reconferidas nesta data contra os PRICING_SOURCE
# de cada uma. Nenhum preco subiu: toda entrada verificavel esta igual ou ACIMA
# do mercado, entao a tabela segue sendo teto conservador -- que e a unica
# propriedade que ela precisa ter. Reconferencia de 2026-08-10:
#   gpt-5.6-terra    tabela 2.50/15  | catalogo 1/6      -> tabela acima
#   claude-sonnet-5  tabela 3/15     | catalogo 2/10     -> tabela acima
#   gemini-2.5-pro   tabela 1.25/10  | fonte 1.25/10     -> exato (faixa <=200k,
#                    garantida por MAX_INPUT_TOKENS = 200_000)
#   gpt-5.6-sol      tabela 5/30     | catalogo 5/30     -> exato
#   gpt-5.6-luna     tabela 1/6      | catalogo 0.10/0.60-> tabela acima
#   gemini-3.5-flash tabela 0.30/2.50| catalogo 0.30/2.50-> exato
#   claude opus      tabela 5/25     | catalogo 5/25     -> exato
#   gemini-3.1-pro   sem tabela publica; segue no teto da familia Pro
# ESTE VALOR EXPIRA EM 7 DIAS (PRICING_MAX_AGE_S). Vencido, o motor recusa
# arrancar -- por desenho: preco velho e contencao monetaria velha. Renovar
# exige RECONFERIR os precos, nao so mexer no numero.
PRICING_CAPTURADO_EM = 1_786_320_000
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
class OrcamentoMoeda:
    repositorio: RepositorioOrcamento
    teto_bootstrap: Decimal


@dataclass(frozen=True)
class DependenciasOrcamento:
    cliente: ClienteSomenteOrcado
    orcamentos: dict[Moeda, OrcamentoMoeda]
    fabrica: Callable[
        [str, str, int, RequisitosTentativaCusteada], list[RotaTentativaCusteada]
    ]
    rotas_certificadas: tuple[RotaOrcadaCertificada, ...]


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


def _teto_token(dados: dict) -> Decimal:
    bruto = dados.get("teto_bootstrap_token")
    if not isinstance(bruto, str) or re.fullmatch(r"[1-9][0-9]{0,15}", bruto) is None:
        raise ErroOrcamento("teto_bootstrap_token invalido")
    return Decimal(bruto)


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
        return [RotaTentativaCusteada(
            "openai:gpt-5", "openai", adaptador, moeda="BRL",
        )]

    return DependenciasOrcamento(
        cliente=ClienteSomenteOrcado(),
        orcamentos={"BRL": OrcamentoMoeda(
            RepositorioOrcamento(Path(workspace) / "orcamento"), teto_bootstrap,
        )},
        fabrica=fabricar,
        rotas_certificadas=(RotaOrcadaCertificada(
            "openai:gpt-5", "openai", frozenset({"executor", "verifier"}),
        ),),
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
            return [RotaTentativaCusteada(
                route_id, provider_id, adaptador, moeda="BRL",
            )]
        return []

    return DependenciasOrcamento(
        cliente=_ClienteMultiSomenteOrcado(),
        orcamentos={"BRL": OrcamentoMoeda(
            RepositorioOrcamento(Path(workspace) / "orcamento"), teto_bootstrap,
        )},
        fabrica=fabricar,
        rotas_certificadas=(
            # Catalogo certificado: so os papeis que a independencia governa.
            # `openai` aparece nos dois lados de proposito -- ela executa em alta
            # complexidade e julga no caminho normal. A validacao exige que
            # EXISTA um par com providers distintos (google x openai), e o
            # `evitar_provedor` garante em runtime que ela nunca julga a si mesma.
            RotaOrcadaCertificada("google:gemini-2.5-pro", "google", frozenset({"executor"})),
            RotaOrcadaCertificada("openai:gpt-5", "openai", frozenset({"executor", "verifier"})),
            RotaOrcadaCertificada("anthropic:sonnet-4-5", "anthropic", frozenset({"verifier"})),
        ),
    )


# --------------------------------------------------------------------------
# Composicao via OmniRoute (proxy OpenAI-compativel)
# --------------------------------------------------------------------------
#
# Alcanca Gemini, GPT e Claude com uma credencial so. A concessao esta em
# `omniroute_orcado`: `provider_id` passa a ser DECLARADO, nao observado, entao
# o motor nao consegue mais verificar sozinho que executor e verifier sao mesmo
# modelos diferentes. Produtor != juiz vira promessa do proxy. Serve para MVP;
# nao serve para o curador decidir promocao de modelo.

_ESPERADOS_OMNI = {
    "omniroute", "fx", "fx_max_age_s", "margem", "timeout",
}
_ESPERADOS_BLOCO_OMNI = {"base_url", "api_key_env", "papeis"}
_ESPERADOS_BLOCO_OMNI_SEM_CREDENCIAL = {"base_url", "sem_credencial", "papeis"}
_ESPERADOS_PAPEL_OMNI = {
    "modelo", "provider_id", "max_completion_tokens", "max_input_tokens",
}


class _ClienteOmniSomenteOrcado(ClienteSomenteOrcado):
    provedor = "omniroute"
    modelo = "roteado"


def _rota_omniroute(*, moeda: Moeda, **kwargs: Any) -> RotaTentativaCusteada:
    """Monta uma rota custeada; o route_id sai do nome do modelo, saneado."""
    modelo = str(kwargs["modelo"])
    provider_id = str(kwargs.pop("provider_id"))
    return RotaTentativaCusteada(
        re.sub(r"[^a-z0-9_.:-]", "-", modelo.lower()),
        provider_id,
        ClienteOmniRouteCusteado(**kwargs),
        moeda=moeda,
    )


def compor_orcamento_omniroute(
    cfg: dict, workspace: str | Path, *,
    relogio: Callable[[], int] = lambda: int(time.time()),
    transporte: Any = None,
) -> DependenciasOrcamento:
    bloco_raiz = cfg if isinstance(cfg, dict) else None
    if not isinstance(bloco_raiz, dict) or not _ESPERADOS_OMNI <= set(bloco_raiz):
        raise ErroOrcamento("configuracao orcada ausente ou invalida")
    bloco = bloco_raiz["omniroute"]
    if not isinstance(bloco, dict):
        raise ErroOrcamento("bloco omniroute ausente ou invalido")

    base_url = _texto(bloco, "base_url")
    if set(bloco) == _ESPERADOS_BLOCO_OMNI:
        env: str | None = _texto(bloco, "api_key_env")
    elif set(bloco) == _ESPERADOS_BLOCO_OMNI_SEM_CREDENCIAL:
        if type(bloco["sem_credencial"]) is not bool or not bloco["sem_credencial"]:
            raise ErroOrcamento("bloco omniroute ausente ou invalido")
        env = None
    else:
        raise ErroOrcamento("bloco omniroute ausente ou invalido")
    if (
        env is not None
        and (re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", env) is None
             or not os.environ.get(env))
    ):
        raise ErroOrcamento("credencial omniroute ausente")

    papeis_bruto = bloco["papeis"]
    if not isinstance(papeis_bruto, dict) or not papeis_bruto:
        raise ErroOrcamento("papeis omniroute invalidos")
    # Cada papel carrega uma LISTA de alternativas em ordem de preferencia. Isso
    # nao e luxo: o motor passa `evitar_provedor` com o provedor que PRODUZIU o
    # no, e um papel com uma alternativa so fica sem rota sempre que o produtor
    # coincide com ele. Com Anthropic planejando, um verifier exclusivamente
    # Anthropic nunca roda -- foi exatamente o que derrubou a missao antes.
    papeis: dict[str, list[tuple[str, str, int, int, Moeda]]] = {}
    moedas_usadas: set[Moeda] = set()
    for papel, bruto in papeis_bruto.items():
        itens = bruto if isinstance(bruto, list) else [bruto]
        if not isinstance(papel, str) or not itens:
            raise ErroOrcamento(f"papel omniroute invalido: {papel}")
        alternativas: list[tuple[str, str, int, int, Moeda]] = []
        for item in itens:
            if not isinstance(item, dict) or set(item) != _ESPERADOS_PAPEL_OMNI:
                raise ErroOrcamento(f"papel omniroute invalido: {papel}")
            modelo = _texto(item, "modelo")
            resolucao = omniroute_orcado.resolver_modelo(modelo)
            moedas_usadas.add(resolucao.moeda)
            provider_id = _texto(item, "provider_id")
            if re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", provider_id) is None:
                raise ErroOrcamento(f"provider_id invalido: {provider_id}")
            # O `provider_id` da config nao pode contradizer quem TREINOU o
            # modelo. O OmniRoute serve o mesmo Opus 4.6 por `claude/` e por
            # `agy/`; sem esta checagem, declarar a rota `agy/` como "google"
            # fazia executor e verifier passarem na independencia sendo o mesmo
            # modelo -- dois julgamentos que erram identico contados como dois.
            if provider_id != resolucao.vendor:
                raise ErroOrcamento(
                    f"provider_id {provider_id} contradiz o vendor de {modelo}"
                    f" ({resolucao.vendor})")
            alternativas.append((
                modelo, provider_id,
                _inteiro(item, "max_completion_tokens"),
                _inteiro(item, "max_input_tokens",
                         maximo=omniroute_orcado.MAX_INPUT_TOKENS),
                resolucao.moeda,
            ))
        papeis[papel] = alternativas

    for obrigatorio in ("executor", "verifier"):
        if obrigatorio not in papeis:
            raise ErroOrcamento(f"papel {obrigatorio} ausente")

    fx_bruto = bloco_raiz["fx"]
    if not isinstance(fx_bruto, dict) or set(fx_bruto) != {
        "versao", "capturado_em", "cotacao_venda"
    }:
        raise ErroOrcamento("snapshot FX invalido")
    fx_versao = _texto(fx_bruto, "versao")
    fx_capturado = _inteiro(fx_bruto, "capturado_em")
    fx_cotacao = _decimal(fx_bruto, "cotacao_venda")
    fx_max_age = _inteiro(bloco_raiz, "fx_max_age_s", maximo=FX_MAX_AGE_LIMITE_S)
    # Frescor conferido AQUI, e não só na primeira chamada. O cliente é
    # construído por chamada, dentro de `fabricar`, então snapshot vencido só
    # aparecia depois de o motor já ter planejado e começado a executar -- e
    # aparecia como "falha externa do executor", três vezes, sem o motivo. A
    # checagem por chamada continua: uma run longa pode vencer no meio dela.
    if "BRL" in moedas_usadas:
        omniroute_orcado.exigir_snapshot_fresco(
            "FX", fx_versao, fx_capturado, fx_max_age, relogio(),
        )
        omniroute_orcado.exigir_snapshot_fresco(
            "pricing", omniroute_orcado.PRICING_VERSION, PRICING_CAPTURADO_EM,
            PRICING_MAX_AGE_S, relogio(),
        )
    if "TOKEN" in moedas_usadas:
        omniroute_orcado.exigir_rotas_gratis_frescas(relogio())
    timeout = _inteiro(bloco_raiz, "timeout", maximo=600)
    margem = _decimal(bloco_raiz, "margem")
    raiz_orcamento = Path(workspace) / "orcamento"
    orcamentos: dict[Moeda, OrcamentoMoeda] = {}
    if "BRL" in moedas_usadas:
        orcamentos["BRL"] = OrcamentoMoeda(
            RepositorioOrcamento(raiz_orcamento),
            _decimal(bloco_raiz, "teto_bootstrap_brl"),
        )
    if "TOKEN" in moedas_usadas:
        orcamentos["TOKEN"] = OrcamentoMoeda(
            RepositorioOrcamento(raiz_orcamento, moeda="TOKEN"),
            _teto_token(bloco_raiz),
        )

    kwargs = {} if transporte is None else {"transporte": transporte}

    def fabricar(
        papel: str, prompt: str, _tentativa: int, requisitos: RequisitosTentativaCusteada,
    ) -> list[RotaTentativaCusteada]:
        if requisitos.ferramentas is not None:
            return []
        # `papel` de subagente e campo livre que o planner inventa (pesquisador,
        # redator, analista...); nenhuma config enumera todos. Quem a certificacao
        # governa e o ESTAGIO, e subagente e executor por construcao — sem este
        # fallback, todo subagente de spec gerada fica sem rota. Nao e improviso
        # como no arranjo multi: aqui `papeis` e config do operador, entao papel
        # declarado continua vencendo e so o silencio cai no executor.
        alternativas = papeis.get(papel) or papeis["executor"]
        candidatas = [
            alt for alt in alternativas if requisitos.evitar_provedor != alt[1]
        ]
        if not candidatas:
            return []
        api_key = os.environ.get(env) if env is not None else None
        if env is not None and not api_key:
            raise ErroOrcamento("credencial omniroute ausente")
        # Devolve a CADEIA inteira, nao so a preferida: `chamar_orcado` percorre
        # a lista em ordem e cai na proxima quando uma rota falha. Devolver um
        # item so jogava esse failover fora -- bastava o provedor preferido estar
        # sem cota para o papel inteiro morrer, com "modelo nao respondeu".
        rotas: list[RotaTentativaCusteada] = []
        for modelo, provider_id, tokens, entrada_max, moeda in candidatas:
            rotas.append(_rota_omniroute(
                moeda=moeda,
                provider_id=provider_id,
                api_key=api_key, base_url=base_url, modelo=modelo, prompt=prompt,
                max_input_tokens=entrada_max, max_completion_tokens=tokens,
                fx=omniroute_orcado.SnapshotFX(fx_versao, fx_capturado, fx_cotacao),
                pricing=omniroute_orcado.SnapshotPricing(
                    omniroute_orcado.PRICING_VERSION, PRICING_CAPTURADO_EM,
                    omniroute_orcado.PRICING_SOURCE,
                ),
                agora=relogio(), fx_max_age_s=fx_max_age,
                pricing_max_age_s=PRICING_MAX_AGE_S, margem=margem,
                timeout=timeout, **kwargs,
            ))
        return rotas

    vistos: dict[str, set[str]] = {}
    for papel in ("executor", "verifier"):
        for modelo, provider_id, _t, _e, _moeda in papeis[papel]:
            vistos.setdefault(f"{modelo}|{provider_id}", set()).add(papel)
    certificadas = tuple(
        RotaOrcadaCertificada(
            re.sub(r"[^a-z0-9_.:-]", "-", chave.split("|")[0].lower()),
            chave.split("|")[1],
            frozenset(usos),
        )
        for chave, usos in vistos.items()
    )
    return DependenciasOrcamento(
        cliente=_ClienteOmniSomenteOrcado(),
        orcamentos=orcamentos,
        fabrica=fabricar,
        rotas_certificadas=certificadas,
    )
