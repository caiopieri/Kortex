"""Adaptador custeado para uma tentativa direta na Anthropic Messages API.

Espelha `openai_orcado.py` de proposito: mesma forma, mesmas guardas, mesma
disciplina de custo derivado SOMENTE do usage devolvido pelo provedor.

ATENCAO -- os precos abaixo sao code-owned e precisam ser verificados contra a
tabela publica antes de qualquer gasto real. `PRICING_VERSION` carrega a data da
verificacao e `PRICING_SOURCE` a origem; a composicao confronta os dois e recusa
snapshot velho. Preco errado aqui e contencao monetaria errada no motor inteiro.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Callable, Mapping, cast

from .orcamento import CotacaoTentativa, ErroOrcamento, ResultadoTentativa


MODELO = "claude-sonnet-5"
VERSAO_API = "2023-06-01"
MAX_INPUT_TOKENS = 200_000
MAX_OUTPUT_TOKENS = 64_000
PRICING_VERSION = "anthropic-sonnet5-standard-verified-2026-07-28"
PRICING_SOURCE = "https://platform.claude.com/docs/en/about-claude/pricing"
# Verificado em 2026-07-28 contra PRICING_SOURCE.
#
# DELIBERADO: o Sonnet 5 esta em preco promocional de $2/$10 ate 2026-08-31, e
# passa a $3/$15 em 01/09. A tabela abaixo usa o preco PROMOCIONAL ENCERRADO,
# nao o vigente. Superfatura ~50% ate agosto e fica exata depois -- errar para
# cima e seguro (o teto so aperta), errar para baixo furaria a unica contencao
# monetaria do sistema exatamente no dia da virada, sem ninguem perceber.
#
# `cache_read` = 0.1x do input; escrita de cache de 5min = 1.25x. As tres linhas
# sao disjuntas no usage da Messages API -- ver `tentar_uma_vez`.
_INPUT_USD = Decimal("3") / Decimal(1_000_000)
_CACHED_USD = Decimal("0.30") / Decimal(1_000_000)
_CACHE_WRITE_USD = Decimal("3.75") / Decimal(1_000_000)
_OUTPUT_USD = Decimal("15") / Decimal(1_000_000)
_QUANTUM_BRL = Decimal("0.000001")


@dataclass(frozen=True)
class SnapshotFX:
    versao: str
    capturado_em: int
    cotacao_venda: Decimal


@dataclass(frozen=True)
class SnapshotPricing:
    versao: str
    capturado_em: int
    fonte: str


RespostaHTTP = tuple[int, Mapping[str, str], bytes]
TransporteHTTP = Callable[[str, bytes, Mapping[str, str], int], RespostaHTTP]


def _inteiro(valor: object, nome: str) -> int:
    if type(valor) is not int or valor < 0:
        raise ErroOrcamento(f"{nome} invalido")
    return valor


def _decimal_positivo(valor: object, nome: str) -> Decimal:
    if type(valor) is not Decimal or not valor.is_finite() or valor <= 0:
        raise ErroOrcamento(f"{nome} invalido")
    return valor


def _arredondar_brl(valor: Decimal) -> Decimal:
    return valor.quantize(_QUANTUM_BRL, rounding=ROUND_CEILING)


def _http_real(url: str, corpo: bytes, headers: Mapping[str, str], timeout: int) -> RespostaHTTP:
    requisicao = urllib.request.Request(url, data=corpo, headers=dict(headers), method="POST")
    with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
        return resposta.status, dict(resposta.headers.items()), resposta.read()


class ClienteAnthropicCusteado:
    """Uma chamada, sem retry, com custo derivado somente do usage do provedor."""

    def __init__(
        self, *, api_key: str, prompt: str, max_input_tokens: int,
        max_completion_tokens: int, fx: SnapshotFX, pricing: SnapshotPricing,
        agora: int, fx_max_age_s: int, pricing_max_age_s: int,
        margem: Decimal, timeout: int, transporte: TransporteHTTP = _http_real,
    ) -> None:
        if not isinstance(api_key, str) or not api_key or not isinstance(prompt, str) or not prompt:
            raise ErroOrcamento("entrada Anthropic invalida")
        self.max_input_tokens = _inteiro(max_input_tokens, "max_input_tokens")
        self.max_completion_tokens = _inteiro(max_completion_tokens, "max_completion_tokens")
        if (self.max_input_tokens != MAX_INPUT_TOKENS
                or self.max_completion_tokens == 0
                or self.max_completion_tokens > MAX_OUTPUT_TOKENS):
            raise ErroOrcamento("limites de token invalidos")
        if len(prompt.encode("utf-8")) > self.max_input_tokens:
            raise ErroOrcamento("prompt excede limite conservador")
        if (type(agora) is not int or type(fx_max_age_s) is not int or fx_max_age_s <= 0
                or type(pricing_max_age_s) is not int or pricing_max_age_s <= 0):
            raise ErroOrcamento("janela de snapshot invalida")
        if type(fx) is not SnapshotFX or not fx.versao or type(fx.capturado_em) is not int:
            raise ErroOrcamento("snapshot FX invalido")
        if fx.capturado_em > agora or agora - fx.capturado_em > fx_max_age_s:
            raise ErroOrcamento("snapshot FX stale")
        if (type(pricing) is not SnapshotPricing
                or pricing.versao != PRICING_VERSION or pricing.fonte != PRICING_SOURCE
                or type(pricing.capturado_em) is not int):
            raise ErroOrcamento("snapshot pricing invalido")
        if pricing.capturado_em > agora or agora - pricing.capturado_em > pricing_max_age_s:
            raise ErroOrcamento("snapshot pricing stale")
        self.fx, self.pricing = fx, pricing
        self.margem = _decimal_positivo(margem, "margem")
        _decimal_positivo(fx.cotacao_venda, "cotacaoVenda")
        if self.margem < 1:
            raise ErroOrcamento("margem subestima custo")
        if type(timeout) is not int or timeout <= 0 or not callable(transporte):
            raise ErroOrcamento("transporte invalido")
        self._api_key, self._prompt = api_key, prompt
        self._timeout, self._transporte = timeout, transporte

    def _brl(
        self, input_tokens: int, cached_tokens: int, output_tokens: int,
        cache_write_tokens: int = 0, *, margem: bool,
    ) -> Decimal:
        usd = (input_tokens * _INPUT_USD
               + cached_tokens * _CACHED_USD
               + cache_write_tokens * _CACHE_WRITE_USD
               + output_tokens * _OUTPUT_USD)
        multiplicador = self.margem if margem else Decimal(1)
        return _arredondar_brl(usd * self.fx.cotacao_venda * multiplicador)

    def cotar_tentativa(self) -> CotacaoTentativa:
        # Reserva pelo pior caso: todo o input cobrado como escrita de cache, que
        # e a linha mais cara. Subcotar aqui e deixar o teto ser furado.
        maximo = self._brl(
            0, 0, self.max_completion_tokens, self.max_input_tokens, margem=True,
        )
        versao = (
            f"{self.pricing.versao}@{self.pricing.capturado_em}"
            f"+fx:{self.fx.versao}+margin:{self.margem}"
        )
        return CotacaoTentativa(maximo, "BRL", versao)

    def tentar_uma_vez(self) -> ResultadoTentativa:
        payload = {
            "model": MODELO,
            "max_tokens": self.max_completion_tokens,
            "messages": [{"role": "user", "content": self._prompt}],
        }
        status, headers, bruto = self._transporte(
            "https://api.anthropic.com/v1/messages",
            json.dumps(payload, separators=(",", ":")).encode(),
            {
                "x-api-key": self._api_key,
                "anthropic-version": VERSAO_API,
                "Content-Type": "application/json",
            },
            self._timeout,
        )
        if status != 200:
            raise ErroOrcamento("resposta Anthropic ambigua")
        try:
            resposta = cast(dict[str, object], json.loads(bruto))
            if resposta.get("model") != MODELO:
                raise ErroOrcamento("modelo divergente")
            usage = cast(dict[str, object], resposta["usage"])
            # Na Messages API `input_tokens` NAO inclui os tokens de cache: as
            # tres linhas sao disjuntas e cada uma tem preco proprio.
            entrada = _inteiro(usage["input_tokens"], "input_tokens")
            saida = _inteiro(usage["output_tokens"], "output_tokens")
            cached = _inteiro(
                usage.get("cache_read_input_tokens", 0), "cache_read_input_tokens"
            )
            escrita = _inteiro(
                usage.get("cache_creation_input_tokens", 0), "cache_creation_input_tokens"
            )
            if entrada + cached + escrita > self.max_input_tokens:
                raise ErroOrcamento("usage excede limites reservados")
            if saida > self.max_completion_tokens:
                raise ErroOrcamento("usage excede limites reservados")
            blocos = cast(list[object], resposta["content"])
            texto = "".join(
                str(cast(dict[str, object], bloco)["text"])
                for bloco in blocos
                if isinstance(bloco, dict) and bloco.get("type") == "text"
            )
            request_id = next(
                (v for k, v in headers.items() if k.lower() == "request-id"), None
            )
            if not texto or not isinstance(request_id, str):
                raise ErroOrcamento("resposta Anthropic incompleta")
            custo = self._brl(entrada, cached, saida, escrita, margem=False)
            return ResultadoTentativa(texto, custo, "BRL", request_id)
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as erro:
            raise ErroOrcamento("resposta Anthropic invalida") from erro
